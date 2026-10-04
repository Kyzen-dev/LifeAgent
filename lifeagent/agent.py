"""One long-lived Claude Agent SDK client per Telegram chat."""

from __future__ import annotations

import asyncio
import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)
from claude_agent_sdk.types import CanUseToolShadowedWarning

from . import permissions
from .context import AppContext, ToolContext
from .mcp_servers import external_mcp_servers
from .prompts import SYSTEM_PROMPT
from .tools import build_life_server
from .workspace import workspace_skills

log = logging.getLogger(__name__)

# Shadowing is intended: ALLOWED_TOOLS are the read-only tools we never want to ask about.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)

OnTool = Callable[[str, dict[str, Any]], Awaitable[None]]

ERROR_TEXT = {
    "error_max_turns": "کار طولانی‌تر از سقف مجاز شد و نیمه‌کاره ماند. اگر لازم است بگو «ادامه بده».",
    "error_max_budget_usd": "سقف هزینه این درخواست پر شد.",
}


@dataclass
class AgentReply:
    text: str
    cost_usd: float = 0.0
    is_error: bool = False
    tools_used: list[str] = field(default_factory=list)


class ChatAgent:
    def __init__(self, app: AppContext, chat_id: int):
        self.app = app
        self.chat_id = chat_id
        self.lock = asyncio.Lock()
        self.client: ClaudeSDKClient | None = None
        # total_cost_usd in ResultMessage is cumulative for the client's lifetime.
        self._client_cost = 0.0

    # --- options --------------------------------------------------------

    def _options(self, resume: str | None) -> ClaudeAgentOptions:
        s = self.app.settings
        mcp_servers = {
            "life": build_life_server(ToolContext(self.app, self.chat_id)),
            **external_mcp_servers(s),
        }
        return ClaudeAgentOptions(
            model=s.model,
            effort=s.effort,
            thinking={"type": "adaptive"},
            system_prompt=SYSTEM_PROMPT,
            cwd=str(s.workspace_dir),
            # Loads workspace/CLAUDE.md, .claude/skills, .claude/agents, .claude/settings.json
            setting_sources=["project"],
            # Only this workspace's skills, not the CLI's built-in developer skills.
            skills=workspace_skills(s.workspace_dir),
            mcp_servers=mcp_servers,
            allowed_tools=permissions.ALLOWED_TOOLS,
            can_use_tool=self._can_use_tool,
            permission_mode="default",
            resume=resume,
            max_turns=s.max_turns,
            stderr=lambda line: log.debug("cli: %s", line),
        )

    async def _can_use_tool(
        self, tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        s = self.app.settings
        decision = permissions.classify(tool_name, tool_input, s.workspace_dir, s.auto_approve_bash)
        if decision == "allow":
            return PermissionResultAllow(updated_input=tool_input)
        if decision == "deny":
            return PermissionResultDeny(message="دسترسی به مسیرهای بیرون از workspace مجاز نیست.")

        title, details = permissions.describe(tool_name, tool_input)
        if await self.app.approvals.ask(self.chat_id, title, details):
            return PermissionResultAllow(updated_input=tool_input)
        return PermissionResultDeny(
            message="کاربر این کار را تأیید نکرد. آن را انجام نده؛ اگر لازم است راه دیگری پیشنهاد کن."
        )

    # --- lifecycle ------------------------------------------------------

    async def _connect(self, resume: str | None) -> ClaudeSDKClient:
        client = ClaudeSDKClient(self._options(resume))
        await client.connect()
        return client

    async def _ensure_client(self) -> ClaudeSDKClient:
        if self.client is not None:
            return self.client
        session_id = await self.app.db.get_session(self.chat_id)
        try:
            self.client = await self._connect(session_id)
        except Exception:
            if session_id is None:
                raise
            log.warning("could not resume session %s; starting fresh", session_id, exc_info=True)
            await self.app.db.clear_session(self.chat_id)
            self.client = await self._connect(None)
        self._client_cost = 0.0
        return self.client

    async def _drop_client(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                log.debug("disconnect failed", exc_info=True)

    async def interrupt(self) -> bool:
        if self.client is not None and self.lock.locked():
            await self.client.interrupt()
            return True
        return False

    async def reset(self) -> None:
        """Start a brand-new conversation (long-term memory files are kept)."""
        await self.interrupt()
        async with self.lock:
            await self._drop_client()
            await self.app.db.clear_session(self.chat_id)

    async def close(self) -> None:
        await self._drop_client()

    # --- conversation ---------------------------------------------------

    async def ask(self, prompt: str, on_tool: OnTool | None = None) -> AgentReply:
        async with self.lock:
            client = await self._ensure_client()
            try:
                return await self._run(client, prompt, on_tool)
            except Exception:
                # The CLI process may be gone; reconnect (and resume) next time.
                await self._drop_client()
                raise

    async def _run(self, client: ClaudeSDKClient, prompt: str, on_tool: OnTool | None) -> AgentReply:
        await client.query(prompt)
        texts: list[str] = []
        tools_used: list[str] = []
        result: ResultMessage | None = None

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tools_used.append(block.name)
                        if on_tool is not None:
                            try:
                                await on_tool(block.name, block.input)
                            except Exception:  # noqa: BLE001 - progress UI must not break the turn
                                log.debug("progress callback failed", exc_info=True)
                    elif isinstance(block, TextBlock) and message.parent_tool_use_id is None:
                        texts.append(block.text)
            elif isinstance(message, ResultMessage):
                result = message

        if result is None:
            return AgentReply(text="پاسخی دریافت نشد.", is_error=True, tools_used=tools_used)

        await self.app.db.set_session(self.chat_id, result.session_id)
        total = result.total_cost_usd or 0.0
        cost = total - self._client_cost if total >= self._client_cost else total
        self._client_cost = total
        await self.app.db.add_usage(self.chat_id, cost, result.num_turns)

        if result.is_error:
            text = ERROR_TEXT.get(result.subtype) or (
                "خطا در اجرای درخواست: " + "; ".join(result.errors or [result.subtype])
            )
            if texts:
                text = texts[-1] + "\n\n⚠️ " + text
            return AgentReply(text=text, cost_usd=cost, is_error=True, tools_used=tools_used)

        text = (result.result or "").strip() or (texts[-1].strip() if texts else "")
        return AgentReply(text=text or "✅", cost_usd=cost, tools_used=tools_used)


class AgentPool:
    def __init__(self, app: AppContext):
        self.app = app
        self._agents: dict[int, ChatAgent] = {}

    def get(self, chat_id: int) -> ChatAgent:
        agent = self._agents.get(chat_id)
        if agent is None:
            agent = self._agents[chat_id] = ChatAgent(self.app, chat_id)
        return agent

    async def close_all(self) -> None:
        await asyncio.gather(*(a.close() for a in self._agents.values()), return_exceptions=True)
