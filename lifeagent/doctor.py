"""Check that a deployment is wired up correctly: `python -m lifeagent.doctor [--live]`.

Without --live nothing is sent to the model. With --live, one tiny agent turn runs
through the Claude Agent SDK (costs a fraction of a cent) to prove the whole chain.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv

OK, WARN, FAIL = "✅", "⚠️ ", "❌"


class Report:
    def __init__(self) -> None:
        self.failed = False

    def line(self, status: str, name: str, detail: str = "") -> None:
        if status == FAIL:
            self.failed = True
        print(f"{status} {name}" + (f" — {detail}" if detail else ""))


async def _get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    return await client.get(url, timeout=15, **kwargs)


async def run(live: bool) -> int:
    load_dotenv()
    report = Report()
    print("LifeAgent doctor\n")

    # --- configuration ---------------------------------------------------------
    from .config import Settings

    try:
        settings = Settings.from_env()
    except SystemExit as exc:
        report.line(FAIL, "config", str(exc))
        return 1
    report.line(OK, "config", f"model={settings.model} effort={settings.effort} tz={settings.tz}")
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        report.line(FAIL, "Anthropic credentials", "ANTHROPIC_API_KEY is not set")

    from .workspace import ensure_workspace, workspace_skills

    ensure_workspace(settings)
    skills = workspace_skills(settings.workspace_dir)
    report.line(OK if skills else FAIL, "skills", f"{len(skills)} found")
    profile = settings.workspace_dir / "memory" / "profile.md"
    personalized = profile.exists() and "هنوز تکمیل نشده" not in profile.read_text(encoding="utf-8")
    report.line(OK if personalized else WARN, "profile",
                "personal profile in place" if personalized else "template only — onboarding will ask questions")
    data_dir_writable = os.access(settings.data_dir, os.W_OK)
    report.line(OK if data_dir_writable else FAIL, "data dir", str(settings.data_dir))

    async with httpx.AsyncClient() as client:
        # --- Telegram ------------------------------------------------------------
        try:
            r = await _get(client, f"https://api.telegram.org/bot{settings.telegram_token}/getMe")
            data = r.json()
            if data.get("ok"):
                report.line(OK, "Telegram", f"@{data['result']['username']}, allowed users {sorted(settings.allowed_user_ids)}")
            else:
                report.line(FAIL, "Telegram", data.get("description", r.text[:200]))
        except httpx.HTTPError as exc:
            report.line(FAIL, "Telegram", f"unreachable: {exc}")

        # --- Anthropic API reachability (credentials are proven by --live) --------
        try:
            await client.get("https://api.anthropic.com", timeout=15)
            report.line(OK, "api.anthropic.com reachable", "run with --live to verify the key end to end")
        except httpx.HTTPError as exc:
            report.line(FAIL, "api.anthropic.com", f"unreachable: {exc}")

        # --- optional integrations -------------------------------------------------
        if settings.openai_api_key:
            try:
                r = await _get(client, "https://api.openai.com/v1/models",
                               headers={"Authorization": f"Bearer {settings.openai_api_key}"})
                report.line(OK if r.status_code == 200 else FAIL, "OpenAI (voice)", f"HTTP {r.status_code}")
            except httpx.HTTPError as exc:
                report.line(FAIL, "OpenAI (voice)", str(exc))
        else:
            report.line(WARN, "voice messages", "OPENAI_API_KEY not set — voice disabled")

        if settings.github_enabled:
            try:
                r = await _get(client, "https://api.github.com/user",
                               headers={"Authorization": f"Bearer {settings.github_token}"})
                who = r.json().get("login") if r.status_code == 200 else f"HTTP {r.status_code}"
                report.line(OK if r.status_code == 200 else FAIL, "GitHub", str(who))
            except httpx.HTTPError as exc:
                report.line(FAIL, "GitHub", str(exc))
        else:
            report.line(WARN, "GitHub", "not configured")

        if settings.google_enabled:
            report.line(OK if shutil.which("uvx") else FAIL, "Google Workspace MCP",
                        "uvx found" if shutil.which("uvx") else "uvx missing (pip install uv)")
        else:
            report.line(WARN, "Google (Gmail/Calendar/Drive)", "not configured")

        if settings.context7_enabled:
            try:
                await client.get("https://mcp.context7.com/mcp", timeout=15)
                report.line(OK, "Context7", "reachable")
            except httpx.HTTPError as exc:
                report.line(WARN, "Context7", f"unreachable: {exc}")

        from .tools.web import fetch_prayer_times

        try:
            r = await _get(client, "https://api.open-meteo.com/v1/forecast",
                           params={"latitude": 35.69, "longitude": 51.42, "current": "temperature_2m"})
            report.line(OK if r.status_code == 200 else WARN, "weather (Open-Meteo)", f"HTTP {r.status_code}")
        except httpx.HTTPError as exc:
            report.line(WARN, "weather (Open-Meteo)", str(exc))

    if settings.prayer_reminders:
        try:
            times = await fetch_prayer_times(datetime.now(settings.tz).date(), settings.prayer_city,
                                             settings.prayer_country, settings.prayer_method)
            report.line(OK, "prayer times", ", ".join(f"{k} {v}" for k, v in times.items() if k in settings.prayer_names))
        except Exception as exc:  # noqa: BLE001
            report.line(WARN, "prayer times", f"aladhan.com failed: {exc}")

    # --- live agent turn -----------------------------------------------------------
    if live:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            model=settings.model, max_turns=1, allowed_tools=[], setting_sources=[],
            cwd=str(settings.workspace_dir),
        )
        try:
            result = None
            async for message in query(prompt="Reply with exactly: OK", options=options):
                if isinstance(message, ResultMessage):
                    result = message
            if result and not result.is_error:
                report.line(OK, "Claude Agent SDK (live)",
                            f"reply={result.result!r} cost=${(result.total_cost_usd or 0):.4f}")
            else:
                report.line(FAIL, "Claude Agent SDK (live)", str(result.errors if result else "no result"))
        except Exception as exc:  # noqa: BLE001
            report.line(FAIL, "Claude Agent SDK (live)", f"{type(exc).__name__}: {exc}")

    print("\n" + ("Some required checks failed." if report.failed else "All required checks passed."))
    return 1 if report.failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also run one tiny real agent turn")
    sys.exit(asyncio.run(run(parser.parse_args().live)))


if __name__ == "__main__":
    main()
