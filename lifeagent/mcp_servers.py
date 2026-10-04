"""External MCP servers wired into the agent, each enabled from .env."""

from __future__ import annotations

from typing import Any

from .config import Settings


def external_mcp_servers(settings: Settings) -> dict[str, dict[str, Any]]:
    servers: dict[str, dict[str, Any]] = {}

    if settings.google_enabled:
        # https://github.com/taylorwilsdon/google_workspace_mcp — runs as a stdio
        # child of the Claude CLI. Its OAuth callback listens on WORKSPACE_MCP_PORT;
        # see README for the one-time login over an SSH tunnel.
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": settings.google_client_id or "",
            "GOOGLE_OAUTH_CLIENT_SECRET": settings.google_client_secret or "",
            "OAUTHLIB_INSECURE_TRANSPORT": "1",
        }
        if settings.google_user_email:
            env["USER_GOOGLE_EMAIL"] = settings.google_user_email
        servers["google"] = {
            "type": "stdio",
            "command": "uvx",
            "args": [
                "workspace-mcp",
                "--tool-tier", "core",
                "--tools", "gmail", "calendar", "drive", "tasks", "docs", "sheets",
            ],
            "env": env,
        }

    if settings.github_enabled:
        # Official GitHub MCP server (remote).
        servers["github"] = {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {settings.github_token}",
                "X-MCP-Toolsets": settings.github_toolsets,
            },
        }

    if settings.context7_enabled:
        # Up-to-date library/framework documentation (https://github.com/upstash/context7).
        server: dict[str, Any] = {"type": "http", "url": "https://mcp.context7.com/mcp"}
        if settings.context7_api_key:
            server["headers"] = {"Authorization": f"Bearer {settings.context7_api_key}"}
        servers["context7"] = server

    if settings.browser_enabled:
        # Headless Chromium for JS-heavy pages (https://github.com/microsoft/playwright-mcp).
        # Requires the image to be built with INSTALL_BROWSER=true.
        servers["browser"] = {
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y", "@playwright/mcp@latest",
                "--headless", "--isolated", "--no-sandbox",
                "--executable-path", "/usr/bin/chromium",
            ],
        }

    return servers
