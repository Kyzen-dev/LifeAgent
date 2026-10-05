"""Which tool calls run freely and which need a tap on "✅ تأیید" in Telegram.

Policy: reading is free, anything with an external side effect asks first.
Tools listed in ALLOWED_TOOLS are auto-approved by the CLI before the
can_use_tool callback runs; every other call is classified here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from .mcp_servers import SEARCH_SERVERS
from .tools import SERVER_NAME

Decision = Literal["allow", "ask", "deny"]

ALLOWED_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    "Task",
    "Agent",
    "Skill",
    "BashOutput",
    "TaskOutput",
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    f"mcp__{SERVER_NAME}",  # local personal-data tools (SQLite) are always allowed
    "mcp__context7",  # documentation lookup only
]



def allowed_tools(mcp_servers: dict[str, Any]) -> list[str]:
    """ALLOWED_TOOLS plus the read-only search servers present in this session."""
    return ALLOWED_TOOLS + [f"mcp__{name}" for name in SEARCH_SERVERS if name in mcp_servers]


# MCP tool names that only read (Gmail/Calendar/Drive/GitHub naming conventions).
READ_PREFIXES = (
    "get_", "list_", "search_", "read_", "query_", "check_", "fetch_", "find_", "inspect_",
)

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Playwright MCP actions that only look at pages; clicking/typing/uploading asks first.
BROWSER_READ_ACTIONS = {
    "browser_navigate", "browser_navigate_back", "browser_snapshot", "browser_take_screenshot",
    "browser_wait_for", "browser_tabs", "browser_console_messages", "browser_network_requests",
    "browser_resize", "browser_hover", "browser_close",
}

TOOL_LABELS = {
    "Bash": "اجرای دستور در سرور",
    "Write": "نوشتن فایل",
    "Edit": "ویرایش فایل",
    "MultiEdit": "ویرایش فایل",
}


def classify(tool_name: str, tool_input: dict[str, Any], workspace: Path, auto_bash: bool) -> Decision:
    if tool_name in FILE_TOOLS:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        path = (workspace / raw).resolve()
        if not path.is_relative_to(workspace):
            return "deny"
        rel = path.relative_to(workspace)
        # Notes, memory, inbox/outbox: free. The agent's own config needs a nod.
        if rel.parts and rel.parts[0] == ".claude" or rel.name == "CLAUDE.md":
            return "ask"
        return "allow"

    if tool_name == "Bash":
        return "allow" if auto_bash else "ask"

    if tool_name.startswith("mcp__"):
        _, server, action = tool_name.split("__", 2) if tool_name.count("__") >= 2 else ("", "", "")
        if server == "browser":
            return "allow" if action in BROWSER_READ_ACTIONS else "ask"
        return "allow" if action.startswith(READ_PREFIXES) else "ask"

    return "ask"


def trustable(tool_name: str) -> bool:
    """Whether the approval prompt may offer "allow for N minutes".

    Local actions (shell, workspace files, browser interaction) can be trusted for a
    while; anything that talks to other people or services (email, calendar, GitHub)
    is confirmed one call at a time.
    """
    return tool_name == "Bash" or tool_name in FILE_TOOLS or tool_name.startswith("mcp__browser__")


def describe(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, str]:
    """Human-readable (title, details) for the approval prompt."""
    if tool_name == "Bash":
        details = tool_input.get("command", "")
        if tool_input.get("description"):
            details = f"# {tool_input['description']}\n{details}"
        return TOOL_LABELS["Bash"], details

    if tool_name in FILE_TOOLS:
        path = tool_input.get("file_path", "")
        body = tool_input.get("content") or tool_input.get("new_string") or ""
        return TOOL_LABELS.get(tool_name, tool_name), f"{path}\n\n{body}"

    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        server, action = (parts[1], parts[2]) if len(parts) == 3 else ("?", tool_name)
        title = f"{server} → {action}"
    else:
        title = tool_name

    lines = []
    for key, value in tool_input.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, indent=1)
        lines.append(f"{key}: {value}")
    return title, "\n".join(lines)
