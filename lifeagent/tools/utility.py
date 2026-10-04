"""Date conversion and sending generated files back to the user."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from .common import DATE, STR, ok, safe, schema

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def build(ctx: ToolContext) -> list:
    workspace = ctx.settings.workspace_dir

    @tool(
        "date_convert",
        "تبدیل دقیق تاریخ بین شمسی و میلادی و نام روز هفته. برای محاسبه تاریخ‌ها "
        "از ذهن حدس نزن؛ از این ابزار استفاده کن.",
        schema({"date": DATE}, ["date"]),
    )
    @safe
    async def date_convert(args: dict[str, Any]) -> dict[str, Any]:
        day = jalali.parse_date(args["date"])
        return ok(
            {
                "gregorian": day.isoformat(),
                "jalali": jalali.to_jalali_str(day),
                "weekday_fa": jalali.WEEKDAYS_FA[day.weekday()],
                "days_from_today": (day - ctx.now().date()).days,
            }
        )

    @tool(
        "send_file",
        "ارسال یک فایل از workspace (مثلاً outbox/report.pdf یا نمودار PNG) برای کاربر در تلگرام.",
        schema(
            {
                "path": {"type": "string", "description": "مسیر نسبی داخل workspace یا مسیر مطلق داخل آن"},
                "caption": STR,
            },
            ["path"],
        ),
    )
    @safe
    async def send_file(args: dict[str, Any]) -> dict[str, Any]:
        path = (workspace / args["path"]).resolve()
        if not path.is_relative_to(workspace) or not path.is_file():
            raise ValueError(f"فایل داخل workspace پیدا نشد: {args['path']}")
        caption = (args.get("caption") or "")[:1000] or None
        bot = ctx.app.bot
        with path.open("rb") as fh:
            if path.suffix.lower() in IMAGE_EXTS:
                await bot.send_photo(ctx.chat_id, photo=fh, caption=caption)
            else:
                await bot.send_document(ctx.chat_id, document=fh, filename=path.name, caption=caption)
        return ok({"sent": True, "file": str(Path(path).relative_to(workspace))})

    return [date_convert, send_file]
