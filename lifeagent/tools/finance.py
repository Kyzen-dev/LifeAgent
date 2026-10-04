"""Personal finance: transactions, budgets and monthly summaries."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from ..db import utcnow_iso
from .common import DATE, INT, NUM, STR, ok, safe, schema

CURRENCY = {
    "type": "string",
    "description": "کد ارز: IRT (تومان، پیش‌فرض)، USD، EUR، USDT، ...",
}


def build(ctx: ToolContext) -> list:
    db = ctx.db

    @tool(
        "finance_add_transaction",
        "ثبت یک هزینه یا درآمد. مبلغ همیشه مثبت است؛ نوع را با kind مشخص کن. "
        "اگر کاربر ریال گفت، به تومان تبدیل کن (تقسیم بر ۱۰).",
        schema(
            {
                "kind": {"type": "string", "enum": ["expense", "income"]},
                "amount": NUM,
                "category": {
                    "type": "string",
                    "description": "دسته‌بندی کوتاه فارسی، مثل خوراک، حمل‌ونقل، قبوض، حقوق، اشتراک",
                },
                "date": {**DATE, "description": "پیش‌فرض: امروز"},
                "currency": CURRENCY,
                "account": {"type": "string", "description": "حساب/کارت، اختیاری"},
                "note": STR,
            },
            ["kind", "amount", "category"],
        ),
    )
    @safe
    async def add_transaction(args: dict[str, Any]) -> dict[str, Any]:
        day = jalali.parse_date(args["date"]) if args.get("date") else ctx.now().date()
        tx_id = await db.execute(
            "INSERT INTO transactions (date, kind, amount, currency, category, account, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                day.isoformat(),
                args["kind"],
                float(args["amount"]),
                (args.get("currency") or "IRT").upper(),
                args["category"].strip(),
                args.get("account"),
                args.get("note"),
                utcnow_iso(),
            ),
        )
        return ok({"id": tx_id, "date_jalali": jalali.to_jalali_str(day), "saved": True})

    @tool(
        "finance_list_transactions",
        "فهرست تراکنش‌ها با فیلتر بازه تاریخ، دسته و نوع.",
        schema(
            {
                "start": DATE,
                "end": {**DATE, "description": "شامل همین روز"},
                "category": STR,
                "kind": {"type": "string", "enum": ["expense", "income"]},
                "limit": {**INT, "description": "پیش‌فرض ۵۰"},
            }
        ),
    )
    @safe
    async def list_transactions(args: dict[str, Any]) -> dict[str, Any]:
        where, params = [], []
        if args.get("start"):
            where.append("date >= ?")
            params.append(jalali.parse_date(args["start"]).isoformat())
        if args.get("end"):
            where.append("date <= ?")
            params.append(jalali.parse_date(args["end"]).isoformat())
        if args.get("category"):
            where.append("category = ?")
            params.append(args["category"])
        if args.get("kind"):
            where.append("kind = ?")
            params.append(args["kind"])
        sql = "SELECT * FROM transactions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(int(args.get("limit") or 50))
        rows = await db.fetchall(sql, params)
        for row in rows:
            row["date_jalali"] = jalali.to_jalali_str(jalali.parse_date(row["date"]))
            row.pop("created_at", None)
        return ok(rows)

    @tool(
        "finance_delete_transaction",
        "حذف یک تراکنش اشتباه با شناسه.",
        schema({"id": INT}, ["id"]),
    )
    @safe
    async def delete_transaction(args: dict[str, Any]) -> dict[str, Any]:
        count = await db.execute("DELETE FROM transactions WHERE id = ?", (args["id"],))
        return ok({"deleted": bool(count)})

    @tool(
        "finance_set_budget",
        "تعیین یا تغییر سقف بودجه ماهانه برای یک دسته. مقدار ۰ یعنی حذف بودجه.",
        schema(
            {"category": STR, "monthly_limit": NUM, "currency": CURRENCY},
            ["category", "monthly_limit"],
        ),
    )
    @safe
    async def set_budget(args: dict[str, Any]) -> dict[str, Any]:
        currency = (args.get("currency") or "IRT").upper()
        if float(args["monthly_limit"]) <= 0:
            await db.execute(
                "DELETE FROM budgets WHERE category = ? AND currency = ?",
                (args["category"], currency),
            )
            return ok({"removed": True})
        await db.execute(
            "INSERT INTO budgets (category, currency, monthly_limit) VALUES (?, ?, ?) "
            "ON CONFLICT(category, currency) DO UPDATE SET monthly_limit = excluded.monthly_limit",
            (args["category"], currency, float(args["monthly_limit"])),
        )
        return ok({"saved": True})

    @tool(
        "finance_summary",
        "خلاصه مالی یک ماه شمسی: جمع درآمد و هزینه به تفکیک ارز و دسته، "
        "و مقایسه با بودجه. بدون ورودی = ماه جاری.",
        schema(
            {
                "jalali_year": {**INT, "description": "مثل 1405"},
                "jalali_month": {**INT, "description": "۱ تا ۱۲"},
            }
        ),
    )
    @safe
    async def summary(args: dict[str, Any]) -> dict[str, Any]:
        year, month = jalali.current_jalali_month(ctx.now().date())
        year = int(args.get("jalali_year") or year)
        month = int(args.get("jalali_month") or month)
        start, end = jalali.jalali_month_range(year, month)
        params = (start.isoformat(), end.isoformat())

        totals = await db.fetchall(
            "SELECT kind, currency, SUM(amount) AS total, COUNT(*) AS count FROM transactions "
            "WHERE date >= ? AND date < ? GROUP BY kind, currency",
            params,
        )
        by_category = await db.fetchall(
            "SELECT category, currency, SUM(amount) AS total, COUNT(*) AS count FROM transactions "
            "WHERE kind = 'expense' AND date >= ? AND date < ? "
            "GROUP BY category, currency ORDER BY total DESC",
            params,
        )
        budgets = await db.fetchall("SELECT * FROM budgets")
        spent = {(r["category"], r["currency"]): r["total"] for r in by_category}
        budget_status = [
            {
                **b,
                "spent": spent.get((b["category"], b["currency"]), 0),
                "used_percent": round(
                    100 * spent.get((b["category"], b["currency"]), 0) / b["monthly_limit"]
                ),
            }
            for b in budgets
        ]
        return ok(
            {
                "month": f"{year}/{month:02d}",
                "gregorian_range": [start.isoformat(), end.isoformat()],
                "totals": totals,
                "expenses_by_category": by_category,
                "budgets": budget_status,
            }
        )

    return [add_transaction, list_transactions, delete_transaction, set_budget, summary]
