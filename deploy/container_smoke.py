"""Smoke test run inside the built Docker image (CI): everything the bot needs at runtime.

    docker run --rm --user 1234:1234 -v "$PWD/deploy:/smoke:ro" -v "$PWD/ci-data:/data" \
        lifeagent:ci python /smoke/container_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Run by path, so the image's code directory is not on sys.path by default.
sys.path.insert(0, os.environ.get("LIFEAGENT_APP_DIR", "/app"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:ci-smoke-token")
os.environ.setdefault("TELEGRAM_ALLOWED_USER_IDS", "42")
Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)
    if not condition:
        failures.append(name)


def guarded(name: str, fn) -> None:
    """Run one group of checks; an unexpected crash counts as a failure, not an abort."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(name, False, f"{type(exc).__name__}: {exc}")


def check_fonts() -> None:
    fonts = subprocess.run(["fc-list"], capture_output=True, text=True).stdout
    check("font Vazirmatn installed", "Vazirmatn" in fonts)

    from matplotlib import font_manager

    found = font_manager.findfont("Vazirmatn", fallback_to_default=False)
    check("matplotlib finds Vazirmatn", "azirmatn" in found, found)


def check_pdf() -> None:
    from pypdf import PdfReader
    from weasyprint import HTML

    pdf = Path("/tmp/smoke.pdf")
    HTML(string='<html dir="rtl"><body style="font-family: Vazirmatn">گزارش مالی مهر ۱۴۰۵</body></html>').write_pdf(pdf)
    text = PdfReader(str(pdf)).pages[0].extract_text()
    check("Persian PDF renders", pdf.stat().st_size > 1000 and "۱۴۰۵" in text, f"{pdf.stat().st_size} bytes")


def main() -> None:
    import importlib

    for module in ("weasyprint", "docx", "openpyxl", "pptx", "matplotlib", "arabic_reshaper", "bidi",
                   "pypdf", "youtube_transcript_api", "claude_agent_sdk", "telegram", "apscheduler", "jdatetime"):
        try:
            importlib.import_module(module)
            check(f"import {module}", True)
        except Exception as exc:  # noqa: BLE001
            check(f"import {module}", False, repr(exc))

    for binary in ("uvx", "rg", "git"):
        check(f"binary {binary}", shutil.which(binary) is not None)

    guarded("fonts", check_fonts)
    guarded("persian pdf", check_pdf)
    try:
        asyncio.run(app_checks())
    except Exception as exc:  # noqa: BLE001
        check("app checks", False, f"{type(exc).__name__}: {exc}")

    print(f"\n{len(failures)} failure(s)" + (f": {failures}" if failures else ""))
    sys.exit(1 if failures else 0)


async def app_checks() -> None:
    from lifeagent.agent import AgentPool
    from lifeagent.config import Settings
    from lifeagent.context import AppContext, ToolContext
    from lifeagent.db import Database
    from lifeagent.tools import finance
    from lifeagent.workspace import ensure_workspace, workspace_skills

    settings = Settings.from_env()
    ensure_workspace(settings)
    skills = workspace_skills(settings.workspace_dir)
    check("skills discovered on disk", len(skills) >= 30, str(len(skills)))

    app = AppContext(settings=settings, db=Database(settings.db_path))
    await app.db.connect()
    tools = {t.name: t.handler for t in finance.build(ToolContext(app, 42))}
    result = await tools["finance_add_transaction"]({"kind": "expense", "amount": 1000, "category": "تست"})
    check("SQLite + tools on the data volume", not result.get("is_error"), str(result)[:120])

    agent = AgentPool(app).get(42)
    try:
        client = await asyncio.wait_for(agent._ensure_client(), timeout=180)
        info = await client.get_server_info() or {}
        names = {c.get("name") if isinstance(c, dict) else c for c in info.get("commands", [])}
        agents = {a.get("name") if isinstance(a, dict) else a for a in info.get("agents", [])}
        check("Claude CLI starts and loads workspace skills", {"upwork-growth", "morning-brief"} <= names,
              f"{len(names)} commands")
        check("subagents loaded", {"researcher", "health-coach"} <= agents, str(sorted(agents)))
    except Exception as exc:  # noqa: BLE001
        check("Claude CLI starts and loads workspace skills", False, f"{type(exc).__name__}: {exc}")
    finally:
        await agent.close()
        await app.db.close()


if __name__ == "__main__":
    main()
