"""Tasks and goals."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from ..db import utcnow_iso
from .common import DATE, INT, STR, ok, safe, schema

AREA = {
    "type": "string",
    "description": "حوزه: work, personal, health, finance, learning, family",
}
GOAL_FIELDS = ("title", "area", "why", "target_date", "progress", "status", "notes")


def _with_jalali(rows: list[dict[str, Any]], *fields: str) -> list[dict[str, Any]]:
    for row in rows:
        for name in fields:
            if row.get(name):
                row[f"{name}_jalali"] = jalali.to_jalali_str(jalali.parse_date(row[name]))
    return rows


def build(ctx: ToolContext) -> list:
    db = ctx.db

    @tool(
        "task_add",
        "افزودن کار به فهرست کارها. اولویت: ۱ فوری، ۲ مهم، ۳ عادی (پیش‌فرض)، ۴ روزی.",
        schema(
            {
                "title": STR,
                "due": DATE,
                "priority": {**INT, "minimum": 1, "maximum": 4},
                "area": AREA,
                "notes": STR,
            },
            ["title"],
        ),
    )
    @safe
    async def task_add(args: dict[str, Any]) -> dict[str, Any]:
        due = jalali.parse_date(args["due"]).isoformat() if args.get("due") else None
        task_id = await db.execute(
            "INSERT INTO tasks (title, notes, due, priority, area, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (args["title"], args.get("notes"), due, int(args.get("priority") or 3), args.get("area"), utcnow_iso()),
        )
        return ok({"id": task_id, "saved": True})

    @tool(
        "task_list",
        "فهرست کارها. پیش‌فرض: کارهای باز، مرتب بر اساس سررسید و اولویت. "
        "overdue_only برای کارهای عقب‌افتاده؛ due_before برای کارهای تا یک تاریخ.",
        schema(
            {
                "status": {"type": "string", "enum": ["open", "done", "dropped", "all"]},
                "area": AREA,
                "due_before": DATE,
                "overdue_only": {"type": "boolean"},
                "limit": INT,
            }
        ),
    )
    @safe
    async def task_list(args: dict[str, Any]) -> dict[str, Any]:
        where, params = [], []
        status = args.get("status") or "open"
        if status != "all":
            where.append("status = ?")
            params.append(status)
        if args.get("area"):
            where.append("area = ?")
            params.append(args["area"])
        if args.get("due_before"):
            where.append("due IS NOT NULL AND due <= ?")
            params.append(jalali.parse_date(args["due_before"]).isoformat())
        if args.get("overdue_only"):
            where.append("due IS NOT NULL AND due < ?")
            params.append(ctx.now().date().isoformat())
        sql = "SELECT * FROM tasks"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY due IS NULL, due, priority, id LIMIT ?"
        params.append(int(args.get("limit") or 100))
        return ok(_with_jalali(await db.fetchall(sql, params), "due"))

    @tool(
        "task_update",
        "ویرایش کار: تغییر عنوان، سررسید، اولویت، یادداشت یا وضعیت (done / dropped / open).",
        schema(
            {
                "id": INT,
                "title": STR,
                "due": {**DATE, "description": "رشته خالی = حذف سررسید"},
                "priority": {**INT, "minimum": 1, "maximum": 4},
                "area": AREA,
                "notes": STR,
                "status": {"type": "string", "enum": ["open", "done", "dropped"]},
            },
            ["id"],
        ),
    )
    @safe
    async def task_update(args: dict[str, Any]) -> dict[str, Any]:
        sets, params = [], []
        for field in ("title", "priority", "area", "notes"):
            if field in args:
                sets.append(f"{field} = ?")
                params.append(args[field])
        if "due" in args:
            sets.append("due = ?")
            params.append(jalali.parse_date(args["due"]).isoformat() if args["due"] else None)
        if "status" in args:
            sets += ["status = ?", "done_at = ?"]
            params += [args["status"], utcnow_iso() if args["status"] == "done" else None]
        if not sets:
            raise ValueError("هیچ فیلدی برای تغییر داده نشده")
        count = await db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", [*params, args["id"]])
        return ok({"updated": bool(count)})

    @tool(
        "goal_set",
        "ایجاد یا به‌روزرسانی هدف (OKR/هدف بلندمدت). با id = به‌روزرسانی، بدون id = هدف جدید.",
        schema(
            {
                "id": INT,
                "title": STR,
                "area": AREA,
                "why": {"type": "string", "description": "چرا این هدف مهم است"},
                "target_date": DATE,
                "progress": {**INT, "minimum": 0, "maximum": 100},
                "status": {"type": "string", "enum": ["active", "done", "paused", "dropped"]},
                "notes": STR,
            }
        ),
    )
    @safe
    async def goal_set(args: dict[str, Any]) -> dict[str, Any]:
        # Column names are interpolated below, so only known fields get through.
        values = {k: v for k, v in args.items() if k in GOAL_FIELDS}
        if values.get("target_date"):
            values["target_date"] = jalali.parse_date(values["target_date"]).isoformat()
        goal_id = args.get("id")
        if goal_id is None:
            if not values.get("title"):
                raise ValueError("برای هدف جدید عنوان لازم است")
            cols = list(values) + ["created_at"]
            goal_id = await db.execute(
                f"INSERT INTO goals ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [*values.values(), utcnow_iso()],
            )
            return ok({"id": goal_id, "created": True})
        if not values:
            raise ValueError("هیچ فیلدی برای تغییر داده نشده")
        await db.execute(
            f"UPDATE goals SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
            [*values.values(), goal_id],
        )
        return ok({"id": goal_id, "updated": True})

    @tool(
        "goal_list",
        "فهرست اهداف (پیش‌فرض: فعال).",
        schema({"status": {"type": "string", "enum": ["active", "done", "paused", "dropped", "all"]}}),
    )
    @safe
    async def goal_list(args: dict[str, Any]) -> dict[str, Any]:
        status = args.get("status") or "active"
        if status == "all":
            rows = await db.fetchall("SELECT * FROM goals ORDER BY status, target_date")
        else:
            rows = await db.fetchall(
                "SELECT * FROM goals WHERE status = ? ORDER BY target_date IS NULL, target_date", (status,)
            )
        return ok(_with_jalali(rows, "target_date"))

    return [task_add, task_list, task_update, goal_set, goal_list]
