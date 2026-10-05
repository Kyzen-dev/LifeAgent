"""Check that a deployment is wired up correctly: `python -m lifeagent.doctor [--live] [--model X|all]`.

Without --live nothing is sent to a model. With --live, one tiny agent turn runs
through the Claude Agent SDK (costs a fraction of a cent) to prove the whole chain —
for the default model, a given model alias, or every available model (--model all).
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


async def run(live: bool, model_arg: str | None = None) -> int:
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
    report.line(OK, "config", f"effort={settings.effort} tz={settings.tz}")

    from .models import ModelRegistry

    models = ModelRegistry.load(settings.llm_env, settings.models_file)
    available = models.available()
    if not available:
        report.line(FAIL, "models", "no provider key set (ANTHROPIC_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY, ...)")
        return 1
    default = models.pick(settings.model)
    wanted = models.resolve(settings.model)
    if wanted is None or wanted.key != default.key:
        report.line(WARN, "default model", f"LIFEAGENT_MODEL={settings.model} is unavailable; using {default.alias}")
    report.line(OK, "models", f"default={default.alias} ({models.describe(default)}); available: "
                + ", ".join(m.alias for m in available))
    if settings.fallback_model:
        fallback = models.resolve(settings.fallback_model)
        if fallback and models.is_available(fallback) and fallback.key != default.key:
            report.line(OK, "fallback model", models.describe(fallback))
        else:
            report.line(WARN, "fallback model", f"{settings.fallback_model} is unknown, unavailable or the default")
    if settings.models_file.exists():
        report.line(OK, "custom models", str(settings.models_file))

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

        # --- model endpoints (keys are proven by --live) ------------------------------
        providers = {models.provider(m).name: models.provider(m) for m in available}
        for provider in providers.values():
            base = models.base_url(provider) or "https://api.anthropic.com"
            url = base + "/health/liveliness" if provider.name == "gateway" else base
            try:
                r = await client.get(url, timeout=15)
                status = OK if provider.name != "gateway" or r.status_code == 200 else WARN
                report.line(status, f"{provider.label} reachable", f"{base} (HTTP {r.status_code})")
            except httpx.HTTPError as exc:
                hint = " — is the gateway running? docker compose --profile gateway up -d" if provider.name == "gateway" else ""
                report.line(FAIL, provider.label, f"unreachable: {exc}{hint}")

        # --- optional integrations -------------------------------------------------
        from .voice import speech_config

        stt = speech_config(settings)
        if stt:
            models_url = stt.url.rsplit("/audio/", 1)[0] + "/models"
            try:
                r = await _get(client, models_url, headers={"Authorization": f"Bearer {stt.api_key}"})
                report.line(OK if r.status_code == 200 else FAIL, f"voice ({stt.provider}, {stt.model})",
                            f"HTTP {r.status_code}")
            except httpx.HTTPError as exc:
                report.line(FAIL, f"voice ({stt.provider})", str(exc))
        else:
            report.line(WARN, "voice messages", "GROQ_API_KEY (free) or OPENAI_API_KEY not set — voice disabled")

        if settings.tavily_api_key:
            report.line(OK, "web search MCP", "Tavily (key set)")
        elif any(not models.provider(m).native for m in available):
            report.line(OK, "web search MCP", "Exa keyless tier for non-Claude models (set TAVILY_API_KEY for more)")

        if settings.iran_prices_key:
            from .tools.web import fetch_iran_prices

            try:
                prices = await fetch_iran_prices(settings.iran_prices_key)
                report.line(OK, "Iran market prices (BrsApi)", ", ".join(f"{k}: {len(v)}" for k, v in prices.items()))
            except Exception as exc:  # noqa: BLE001
                report.line(WARN, "Iran market prices (BrsApi)", f"{type(exc).__name__}: {exc}"[:200])

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

    # --- live agent turns -----------------------------------------------------------
    if live:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        if model_arg == "all":
            targets = available
        else:
            target = models.resolve(model_arg) if model_arg else default
            if target is None or not models.is_available(target):
                report.line(FAIL, "live test", f"model {model_arg!r} is unknown or has no key")
                targets = []
            else:
                targets = [target]
        for spec in targets:
            native = models.provider(spec).native
            options = ClaudeAgentOptions(
                model=spec.model_id, max_turns=1, allowed_tools=[], setting_sources=[],
                cwd=str(settings.workspace_dir), env=models.cli_env(spec),
                thinking={"type": "adaptive"} if spec.thinking else (None if native else {"type": "disabled"}),
            )
            name = f"live: {spec.alias} ({models.describe(spec)})"
            try:
                result = None
                async for message in query(prompt="Reply with exactly: OK", options=options):
                    if isinstance(message, ResultMessage):
                        result = message
                if result and not result.is_error:
                    report.line(OK, name, f"reply={(result.result or '').strip()[:40]!r}")
                else:
                    detail = (result.errors or result.result) if result else "no result"
                    report.line(FAIL, name, str(detail)[:300])
            except Exception as exc:  # noqa: BLE001
                report.line(FAIL, name, f"{type(exc).__name__}: {exc}"[:300])

    print("\n" + ("Some required checks failed." if report.failed else "All required checks passed."))
    return 1 if report.failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also run one tiny real agent turn")
    parser.add_argument("--model", help="with --live: a model alias to test, or 'all'")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.live, args.model)))


if __name__ == "__main__":
    main()
