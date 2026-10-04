"""Habits, health metrics and journaling."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from ..db import utcnow_iso
from .common import DATE, INT, NUM, STR, err, ok, safe, schema


def build(ctx: ToolContext) -> list:
    db = ctx.db

    async def _habit_id(name: str) -> int:
        row = await db.fetchone("SELECT id FROM habits WHERE name = ?", (name.strip(),))
        if not row:
            names = [r["name"] for r in await db.fetchall("SELECT name FROM habits WHERE active = 1")]
            raise ValueError(f"عادتی با نام «{name}» نیست. عادت‌های فعال: {names}")
        return row["id"]

    @tool(
        "habit_create",
        "تعریف عادت جدید برای پیگیری (مثل ورزش، مطالعه، مدیتیشن، آب).",
        schema(
            {
                "name": STR,
                "target_per_week": {**INT, "description": "چند روز در هفته؛ پیش‌فرض ۷"},
                "unit": {"type": "string", "description": "واحد اختیاری مثل دقیقه، صفحه، لیوان"},
            },
            ["name"],
        ),
    )
    @safe
    async def habit_create(args: dict[str, Any]) -> dict[str, Any]:
        await db.execute(
            "INSERT INTO habits (name, target_per_week, unit, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET active = 1, target_per_week = excluded.target_per_week, "
            "unit = excluded.unit",
            (args["name"].strip(), int(args.get("target_per_week") or 7), args.get("unit"), utcnow_iso()),
        )
        return ok({"saved": True})

    @tool(
        "habit_archive",
        "غیرفعال کردن عادتی که دیگر پیگیری نمی‌شود.",
        schema({"name": STR}, ["name"]),
    )
    @safe
    async def habit_archive(args: dict[str, Any]) -> dict[str, Any]:
        await db.execute("UPDATE habits SET active = 0 WHERE id = ?", (await _habit_id(args["name"]),))
        return ok({"archived": True})

    @tool(
        "habit_log",
        "ثبت انجام یک عادت در یک روز (پیش‌فرض امروز).",
        schema(
            {
                "name": STR,
                "date": DATE,
                "value": {**NUM, "description": "مقدار (مثلاً ۳۰ دقیقه)؛ پیش‌فرض ۱"},
                "note": STR,
            },
            ["name"],
        ),
    )
    @safe
    async def habit_log(args: dict[str, Any]) -> dict[str, Any]:
        habit_id = await _habit_id(args["name"])
        day = jalali.parse_date(args["date"]) if args.get("date") else ctx.now().date()
        await db.execute(
            "INSERT INTO habit_logs (habit_id, date, value, note) VALUES (?, ?, ?, ?)",
            (habit_id, day.isoformat(), float(args.get("value") or 1), args.get("note")),
        )
        return ok({"logged": True, "date_jalali": jalali.to_jalali_str(day)})

    @tool(
        "habit_status",
        "وضعیت عادت‌های فعال: انجام‌شده‌ها در هفته جاری (از شنبه)، هدف هفتگی، "
        "رشته روزهای پیاپی (streak) و انجام‌شدن امروز.",
        schema({}),
    )
    @safe
    async def habit_status(args: dict[str, Any]) -> dict[str, Any]:
        today = ctx.now().date()
        week_start = jalali.jalali_week_start(today)
        habits = await db.fetchall("SELECT * FROM habits WHERE active = 1 ORDER BY id")
        result = []
        for habit in habits:
            logs = await db.fetchall(
                "SELECT DISTINCT date FROM habit_logs WHERE habit_id = ? AND date >= ? ORDER BY date DESC",
                (habit["id"], (today - timedelta(days=400)).isoformat()),
            )
            days = {row["date"] for row in logs}
            streak, cursor = 0, today if today.isoformat() in days else today - timedelta(days=1)
            while cursor.isoformat() in days:
                streak += 1
                cursor -= timedelta(days=1)
            result.append(
                {
                    "name": habit["name"],
                    "unit": habit["unit"],
                    "target_per_week": habit["target_per_week"],
                    "done_this_week": sum(1 for d in days if d >= week_start.isoformat()),
                    "done_today": today.isoformat() in days,
                    "streak_days": streak,
                }
            )
        return ok(result)

    @tool(
        "health_log",
        "ثبت یک شاخص سلامت: وزن، ساعت خواب، قدم، فشار، ضربان، دقیقه ورزش، کالری، ...",
        schema(
            {
                "metric": {"type": "string", "description": "نام شاخص به انگلیسی کوتاه: weight, sleep_hours, steps, workout_min, ..."},
                "value": NUM,
                "unit": STR,
                "date": DATE,
                "note": STR,
            },
            ["metric", "value"],
        ),
    )
    @safe
    async def health_log(args: dict[str, Any]) -> dict[str, Any]:
        day = jalali.parse_date(args["date"]) if args.get("date") else ctx.now().date()
        await db.execute(
            "INSERT INTO health_logs (date, metric, value, unit, note) VALUES (?, ?, ?, ?, ?)",
            (day.isoformat(), args["metric"].strip().lower(), float(args["value"]), args.get("unit"), args.get("note")),
        )
        return ok({"logged": True})

    @tool(
        "health_history",
        "تاریخچه یک شاخص سلامت در N روز اخیر، به‌همراه میانگین/کمینه/بیشینه.",
        schema({"metric": STR, "days": {**INT, "description": "پیش‌فرض ۳۰"}}, ["metric"]),
    )
    @safe
    async def health_history(args: dict[str, Any]) -> dict[str, Any]:
        since = ctx.now().date() - timedelta(days=int(args.get("days") or 30))
        metric = args["metric"].strip().lower()
        rows = await db.fetchall(
            "SELECT date, value, unit, note FROM health_logs WHERE metric = ? AND date >= ? ORDER BY date",
            (metric, since.isoformat()),
        )
        if not rows:
            known = [r["metric"] for r in await db.fetchall("SELECT DISTINCT metric FROM health_logs")]
            return err(f"داده‌ای برای {metric} نیست. شاخص‌های موجود: {known}")
        values = [r["value"] for r in rows]
        return ok(
            {
                "metric": metric,
                "count": len(values),
                "avg": round(sum(values) / len(values), 2),
                "min": min(values),
                "max": max(values),
                "entries": rows,
            }
        )

    @tool(
        "journal_add",
        "ثبت یادداشت روزانه/ژورنال با حال (mood) و انرژی از ۱ تا ۱۰.",
        schema(
            {
                "text": STR,
                "mood": {**INT, "minimum": 1, "maximum": 10},
                "energy": {**INT, "minimum": 1, "maximum": 10},
                "tags": {"type": "string", "description": "برچسب‌ها با کاما"},
            },
            ["text"],
        ),
    )
    @safe
    async def journal_add(args: dict[str, Any]) -> dict[str, Any]:
        entry_id = await db.execute(
            "INSERT INTO journal (ts, mood, energy, text, tags) VALUES (?, ?, ?, ?, ?)",
            (ctx.now().isoformat(timespec="minutes"), args.get("mood"), args.get("energy"), args["text"], args.get("tags")),
        )
        return ok({"id": entry_id, "saved": True})

    @tool(
        "journal_recent",
        "یادداشت‌های ژورنال N روز اخیر (برای بازبینی و تحلیل روند حال).",
        schema({"days": {**INT, "description": "پیش‌فرض ۷"}, "query": {"type": "string", "description": "جستجوی متنی اختیاری"}}),
    )
    @safe
    async def journal_recent(args: dict[str, Any]) -> dict[str, Any]:
        since = ctx.now() - timedelta(days=int(args.get("days") or 7))
        sql, params = "SELECT * FROM journal WHERE ts >= ?", [since.isoformat(timespec="minutes")]
        if args.get("query"):
            sql += " AND (text LIKE ? OR tags LIKE ?)"
            params += [f"%{args['query']}%"] * 2
        return ok(await db.fetchall(sql + " ORDER BY ts DESC LIMIT 100", params))

    return [
        habit_create, habit_archive, habit_log, habit_status,
        health_log, health_history, journal_add, journal_recent,
    ]
