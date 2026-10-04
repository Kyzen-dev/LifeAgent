"""The in-process `life` MCP server: personal data tools backed by SQLite."""

from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig

from ..context import ToolContext
from . import finance, planning, reminders, utility, wellbeing

SERVER_NAME = "life"


def build_life_server(ctx: ToolContext) -> McpSdkServerConfig:
    tools = [
        *finance.build(ctx),
        *wellbeing.build(ctx),
        *planning.build(ctx),
        *reminders.build(ctx),
        *utility.build(ctx),
    ]
    return create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0", tools=tools)
