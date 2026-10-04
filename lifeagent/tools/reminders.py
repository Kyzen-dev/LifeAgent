"""Time-based reminders delivered as Telegram messages."""

from __future__ import annotations

import re
from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from .common import INT, ok, safe, schema

_DAYS_RE = re.compile(r"^(sat|sun|mon|tue|wed|thu|fri)(,(sat|sun|mon|tue|wed|thu|fri))*$")


def build(ctx: ToolContext) -> list:
    db = ctx.db

    @tool(
        "reminder_add",
        "تنظیم یادآور که سر موعد در تلگرام ارسال می‌شود. برای زمان‌های نسبی "
        "(«دو ساعت دیگر»، «فردا صبح») زمان دقیق را از «اکنون» حساب کن. "
        "repeat: none (یک‌بار)، daily (هر روز همان ساعت)، weekly (روزهای days).",
        schema(
            {
                "text": {"type": "string", "description": "متن یادآوری، کامل و قابل‌فهم"},
                "at": {"type": "string", "description": "زمان اولین اجرا، مثل 1405/07/12 18:30 یا 2026-10-04 18:30"},
                "repeat": {"type": "string", "enum": ["none", "daily", "weekly"]},
                "days": {"type": "string", "description": "برای weekly: مثل sat,mon,wed"},
            },
            ["text", "at"],
        ),
    )
    @safe
    async def reminder_add(args: dict[str, Any]) -> dict[str, Any]:
        run_at = jalali.parse_datetime(args["at"], ctx.settings.tz)
        repeat = args.get("repeat") or "none"
        days = (args.get("days") or "").replace(" ", "").lower() or None
        if days and not _DAYS_RE.match(days):
            raise ValueError("days باید مثل sat,mon,wed باشد")
        if repeat == "none" and run_at <= ctx.now():
            raise ValueError("این زمان گذشته است")
        reminder_id = await ctx.app.scheduler.add_reminder(ctx.chat_id, args["text"], run_at, repeat, days)
        next_run = ctx.app.scheduler.next_run(reminder_id)
        return ok(
            {
                "id": reminder_id,
                "next_run": jalali.human_fa(next_run) if next_run else None,
            }
        )

    @tool("reminder_list", "فهرست یادآورهای فعال و زمان اجرای بعدی.", schema({}))
    @safe
    async def reminder_list(args: dict[str, Any]) -> dict[str, Any]:
        rows = await db.fetchall(
            "SELECT id, text, repeat, days FROM reminders WHERE active = 1 AND chat_id = ? ORDER BY id",
            (ctx.chat_id,),
        )
        for row in rows:
            next_run = ctx.app.scheduler.next_run(row["id"])
            row["next_run"] = jalali.human_fa(next_run) if next_run else None
        return ok(rows)

    @tool("reminder_cancel", "لغو یک یادآور با شناسه.", schema({"id": INT}, ["id"]))
    @safe
    async def reminder_cancel(args: dict[str, Any]) -> dict[str, Any]:
        count = await db.execute(
            "UPDATE reminders SET active = 0 WHERE id = ? AND chat_id = ?", (args["id"], ctx.chat_id)
        )
        ctx.app.scheduler.cancel_reminder(args["id"])
        return ok({"cancelled": bool(count)})

    return [reminder_add, reminder_list, reminder_cancel]

