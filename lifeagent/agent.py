"""One long-lived Claude Agent SDK client per Telegram chat.

The model behind a chat can be switched with /model (any provider in lifeagent.models)
and fails over to LIFEAGENT_FALLBACK_MODEL when the provider is down or out of credit.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
from .models import ModelRegistry, ModelSpec
from .prompts import SYSTEM_PROMPT, model_note
from .tools import build_life_server
from .workspace import workspace_skills

log = logging.getLogger(__name__)

# Shadowing is intended: ALLOWED_TOOLS are the read-only tools we never want to ask about.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)

OnTool = Callable[[str, dict[str, Any]], Awaitable[None]]
OnNotice = Callable[[str], Awaitable[None]]

ERROR_TEXT = {
    "error_max_turns": "کار طولانی‌تر از سقف مجاز شد و نیمه‌کاره ماند. اگر لازم است بگو «ادامه بده».",
    "error_max_budget_usd": "سقف هزینه این درخواست پر شد.",
}

# AssistantMessage.error values, explained to the user.
API_ERROR_TEXT = {
    "authentication_failed": "کلید API این مدل نامعتبر است یا دسترسی ندارد",
    "billing_error": "اعتبار حساب این مدل تمام شده است",
    "rate_limit": "سقف تعداد درخواست پر شده؛ کمی بعد دوباره امتحان کن",
    "server_error": "سرور مدل موقتاً در دسترس نیست",
    "invalid_request": "مدل این درخواست را نپذیرفت",
    "unknown": "خطای ناشناخته از سمت مدل",
}
FAILOVER_ERRORS = {"authentication_failed", "billing_error", "rate_limit", "server_error"}
FAILOVER_STATUS = {401, 402, 403, 408, 429, 500, 502, 503, 504, 529}
FAILOVER_MINUTES = 30


@dataclass
class AgentReply:
    text: str
    cost_usd: float = 0.0
    is_error: bool = False
    tools_used: list[str] = field(default_factory=list)
    api_error: str | None = None
    model: str = ""


class ChatAgent:
    def __init__(self, app: AppContext, chat_id: int):
        self.app = app
        self.chat_id = chat_id
        self.lock = asyncio.Lock()
        self.client: ClaudeSDKClient | None = None
        self.client_spec: ModelSpec | None = None
        # ResultMessage.total_cost_usd and .usage are cumulative for the CLI process.
        self._client_cost = 0.0
        self._client_tokens = (0, 0)
        # tool name -> monotonic deadline, from the "allow for N minutes" button
        self._trusted_until: dict[str, float] = {}
        self._failover_until = 0.0
        self._turn_tools: list[str] = []

    @property
    def models(self) -> ModelRegistry:
        return self.app.models

    # --- model choice ---------------------------------------------------

    async def chosen_spec(self) -> ModelSpec:
        alias = await self.app.db.get_chat_model(self.chat_id)
        return self.models.pick(alias, self.app.settings.model)

    def fallback_spec(self, current: ModelSpec) -> ModelSpec | None:
        spec = self.models.resolve(self.app.settings.fallback_model)
        if spec and self.models.is_available(spec) and spec.key != current.key:
            return spec
        return None

    async def active_spec(self) -> ModelSpec:
        chosen = await self.chosen_spec()
        if time.monotonic() < self._failover_until:
            return self.fallback_spec(chosen) or chosen
        return chosen

    async def set_model(self, alias: str | None) -> tuple[ModelSpec, bool]:
        """Choose this chat's model; returns (spec, whether the conversation was kept)."""
        await self.interrupt()
        async with self.lock:
            before = self.client_spec or await self.active_spec()
            await self.app.db.set_chat_model(self.chat_id, alias)
            self._failover_until = 0.0
            after = await self.chosen_spec()
            if self.client is not None and self.client_spec and self.client_spec.key != after.key:
                await self._drop_client()  # reconnects (and resumes if allowed) on the next turn
            return after, before.provider == after.provider

    # --- options --------------------------------------------------------

    def _options(self, spec: ModelSpec, resume: str | None) -> ClaudeAgentOptions:
        s = self.app.settings
        native = self.models.provider(spec).native
        mcp_servers = {
            "life": build_life_server(ToolContext(self.app, self.chat_id)),
            **external_mcp_servers(s, native_model=native),
        }
        options = ClaudeAgentOptions(
            model=spec.model_id,
            env=self.models.cli_env(spec),
            system_prompt=SYSTEM_PROMPT + model_note(spec, native),
            cwd=str(s.workspace_dir),
            # Loads workspace/CLAUDE.md, .claude/skills, .claude/agents, .claude/settings.json
            setting_sources=["project"],
            # Only this workspace's skills, not the CLI's built-in developer skills.
            skills=workspace_skills(s.workspace_dir),
            mcp_servers=mcp_servers,
            allowed_tools=permissions.allowed_tools(mcp_servers),
            can_use_tool=self._can_use_tool,
            permission_mode="default",
            resume=resume,
            max_turns=s.max_turns,
            stderr=lambda line: log.debug("cli: %s", line),
        )
        if spec.thinking:
            options.thinking = {"type": "adaptive"}
        elif not native:
            # Non-Claude models: no Anthropic thinking parameters on the wire.
            options.thinking = {"type": "disabled"}
        if spec.effort:
            options.effort = s.effort
        if not native:
            # WebSearch is an Anthropic server tool; other providers get a search MCP instead.
            options.disallowed_tools = ["WebSearch"]
        return options

    async def _can_use_tool(
        self, tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        s = self.app.settings
        decision = permissions.classify(tool_name, tool_input, s.workspace_dir, s.auto_approve_bash)
        if decision == "allow":
            return PermissionResultAllow(updated_input=tool_input)
        if decision == "deny":
            return PermissionResultDeny(message="دسترسی به مسیرهای بیرون از workspace مجاز نیست.")

        if self._trusted_until.get(tool_name, 0) > time.monotonic():
            return PermissionResultAllow(updated_input=tool_input)

        title, details = permissions.describe(tool_name, tool_input)
        trust_minutes = s.trust_window_min if permissions.trustable(tool_name) else None
        verdict = await self.app.approvals.ask(self.chat_id, title, details, trust_minutes)
        if verdict == "trust" and trust_minutes:
            self._trusted_until[tool_name] = time.monotonic() + trust_minutes * 60
        if verdict in ("once", "trust"):
            return PermissionResultAllow(updated_input=tool_input)
        return PermissionResultDeny(
            message="کاربر این کار را تأیید نکرد. آن را انجام نده؛ اگر لازم است راه دیگری پیشنهاد کن."
        )

    # --- lifecycle ------------------------------------------------------

    async def _connect(self, spec: ModelSpec, resume: str | None) -> ClaudeSDKClient:
        client = ClaudeSDKClient(self._options(spec, resume))
        await client.connect()
        return client

    async def _ensure_client(self, spec: ModelSpec) -> ClaudeSDKClient:
        if self.client is not None and self.client_spec and self.client_spec.key == spec.key:
            return self.client
        await self._drop_client()
        # A conversation continues across models of the same provider; a different
        # provider starts fresh (long-term memory files are unaffected).
        session_id = await self.app.db.get_session(self.chat_id, spec.provider)
        try:
            self.client = await self._connect(spec, session_id)
        except Exception:
            if session_id is None:
                raise
            log.warning("could not resume session %s; starting fresh", session_id, exc_info=True)
            await self.app.db.clear_session(self.chat_id)
            self.client = await self._connect(spec, None)
        self.client_spec = spec
        self._client_cost = 0.0
        self._client_tokens = (0, 0)
        return self.client

    async def _drop_client(self) -> None:
        client, self.client, self.client_spec = self.client, None, None
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
            self._trusted_until.clear()

    async def close(self) -> None:
        await self._drop_client()

    # --- conversation ---------------------------------------------------

    async def ask(self, prompt: str, on_tool: OnTool | None = None,
                  on_notice: OnNotice | None = None) -> AgentReply:
        async with self.lock:
            spec = await self.active_spec()
            reply, error = await self._attempt(spec, prompt, on_tool)

            fallback = self.fallback_spec(spec)
            reason = self._failover_reason(reply, error)
            # Only retry when nothing has happened yet, so no action runs twice.
            if fallback and reason and not self._turn_tools:
                self._failover_until = time.monotonic() + FAILOVER_MINUTES * 60
                fresh = fallback.provider != spec.provider
                log.warning("model %s failed (%s); failing over to %s", spec.alias, reason, fallback.alias)
                if on_notice is not None:
                    await on_notice(
                        f"⚠️ {spec.label} جواب نداد ({reason}). تا {FAILOVER_MINUTES} دقیقه با "
                        f"{fallback.label} ادامه می‌دهم"
                        + ("؛ این گفتگو با آن مدل از نو شروع می‌شود (حافظه بلندمدت سر جایش است)." if fresh else ".")
                    )
                reply, error = await self._attempt(fallback, prompt, on_tool)

            if error is not None:
                raise error
            return reply

    async def _attempt(self, spec: ModelSpec, prompt: str, on_tool: OnTool | None
                       ) -> tuple[AgentReply | None, Exception | None]:
        self._turn_tools = []
        try:
            client = await self._ensure_client(spec)
            return await self._run(client, spec, prompt, on_tool), None
        except Exception as exc:  # noqa: BLE001
            # The CLI process may be gone; reconnect (and resume) next time.
            log.warning("turn on %s failed", spec.alias, exc_info=True)
            await self._drop_client()
            return None, exc

    @staticmethod
    def _failover_reason(reply: AgentReply | None, error: Exception | None) -> str | None:
        if error is not None:
            return f"{type(error).__name__}"
        if reply is not None and reply.api_error in FAILOVER_ERRORS:
            return API_ERROR_TEXT[reply.api_error]
        return None

    async def _run(self, client: ClaudeSDKClient, spec: ModelSpec, prompt: str,
                   on_tool: OnTool | None) -> AgentReply:
        await client.query(prompt)
        texts: list[str] = []
        api_error: str | None = None
        result: ResultMessage | None = None

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                if message.error and message.parent_tool_use_id is None:
                    api_error = message.error
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        self._turn_tools.append(block.name)
                        if on_tool is not None:
                            try:
                                await on_tool(block.name, block.input)
                            except Exception:  # noqa: BLE001 - progress UI must not break the turn
                                log.debug("progress callback failed", exc_info=True)
                    elif isinstance(block, TextBlock) and message.parent_tool_use_id is None:
                        texts.append(block.text)
            elif isinstance(message, ResultMessage):
                result = message

        tools_used = list(self._turn_tools)
        if result is None:
            return AgentReply(text="پاسخی دریافت نشد.", is_error=True, tools_used=tools_used,
                              api_error=api_error, model=spec.alias)
        if api_error is None and result.is_error and result.api_error_status in FAILOVER_STATUS:
            api_error = "rate_limit" if result.api_error_status == 429 else (
                "authentication_failed" if result.api_error_status in (401, 403) else
                "billing_error" if result.api_error_status == 402 else "server_error")

        await self.app.db.set_session(self.chat_id, result.session_id, spec.provider)
        cost, tokens_in, tokens_out = self._account(spec, result)
        await self.app.db.add_usage(self.chat_id, cost, result.num_turns, spec.alias, tokens_in, tokens_out)

        if api_error:
            detail = "; ".join(result.errors or []) or (texts[-1].strip() if texts else "")
            text = f"⚠️ {API_ERROR_TEXT.get(api_error, api_error)} ({spec.label})."
            if detail:
                text += f"\n`{detail[:300]}`"
            return AgentReply(text=text, cost_usd=cost, is_error=True, tools_used=tools_used,
                              api_error=api_error, model=spec.alias)

        if result.is_error:
            text = ERROR_TEXT.get(result.subtype) or (
                "خطا در اجرای درخواست: " + "; ".join(result.errors or [result.subtype])
            )
            if texts:
                text = texts[-1] + "\n\n⚠️ " + text
            return AgentReply(text=text, cost_usd=cost, is_error=True, tools_used=tools_used, model=spec.alias)

        text = (result.result or "").strip() or (texts[-1].strip() if texts else "")
        return AgentReply(text=text or "✅", cost_usd=cost, tools_used=tools_used, model=spec.alias)

    def _account(self, spec: ModelSpec, result: ResultMessage) -> tuple[float, int, int]:
        """This turn's cost and tokens (the CLI reports running totals for its process)."""
        usage = result.usage or {}
        total_in = sum(int(usage.get(k) or 0) for k in
                       ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        total_out = int(usage.get("output_tokens") or 0)
        prev_in, prev_out = self._client_tokens
        if total_in < prev_in or total_out < prev_out:  # counter restarted
            prev_in = prev_out = 0
        self._client_tokens = (total_in, total_out)
        tokens_in, tokens_out = total_in - prev_in, total_out - prev_out

        if self.models.provider(spec).native:
            total = result.total_cost_usd or 0.0
            cost = total - self._client_cost if total >= self._client_cost else total
            self._client_cost = total
        else:
            cost = self.models.estimate_cost(
                spec, {"input_tokens": tokens_in, "output_tokens": tokens_out}
            ) or 0.0
        return cost, tokens_in, tokens_out


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
