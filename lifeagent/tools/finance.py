"""Personal finance: transactions (from text, receipts, bank SMS), budgets and summaries."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from claude_agent_sdk import tool
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .. import jalali
from ..context import ToolContext
from ..db import utcnow_iso
from ..formatting import fa_number
from .common import DATE, INT, NUM, STR, ok, safe, schema

log = logging.getLogger(__name__)

# A short, stable category list keeps monthly reports meaningful. Other names are
# accepted, but the tool points out that a new category was created.
EXPENSE_CATEGORIES = [
    "خوراک", "رستوران و کافه", "حمل‌ونقل", "قبوض و شارژ", "مسکن", "سلامت", "ورزش",
    "آموزش", "اشتراک و نرم‌افزار", "تجهیزات کار", "پوشاک", "خانه", "تفریح و سفر",
    "هدیه و خیریه", "کارمزد", "سایر",
]
INCOME_CATEGORIES = ["پروژه", "حقوق", "فروش", "هدیه", "سود سرمایه", "سایر"]

SOURCES = ["manual", "receipt", "invoice", "bank_sms", "voice", "forward", "import"]

# Spellings the model or the user may use, mapped to the stored code.
CURRENCY_ALIASES = {
    "IRT": "IRT", "TOMAN": "IRT", "TOMANS": "IRT", "تومان": "IRT", "تومن": "IRT",
    "IRR": "IRR", "RIAL": "IRR", "RIALS": "IRR", "ریال": "IRR",
    "$": "USD", "دلار": "USD", "€": "EUR", "یورو": "EUR", "تتر": "USDT",
}
CURRENCY_FA = {"IRT": "تومان", "USD": "دلار", "EUR": "یورو", "USDT": "تتر", "AED": "درهم", "TRY": "لیر"}

CURRENCY = {
    "type": "string",
    "description": "IRT (تومان، پیش‌فرض)، IRR (ریال: خودکار به تومان تبدیل می‌شود)، USD، EUR، USDT، AED، ...",
}
ITEMS = {
    "type": "array",
    "description": "اقلام رسید (اختیاری)",
    "items": {
        "type": "object",
        "properties": {
            "name": STR,
            "qty": NUM,
            "price": {**NUM, "description": "قیمت کل این قلم، به همان ارز تراکنش"},
        },
        "required": ["name"],
    },
}

TX_FIELDS: dict[str, Any] = {
    "kind": {"type": "string", "enum": ["expense", "income"]},
    "amount": {**NUM, "description": "مبلغ مثبت، به ارز currency"},
    "category": {
        "type": "string",
        "description": "هزینه: " + "، ".join(EXPENSE_CATEGORIES) + " | درآمد: " + "، ".join(INCOME_CATEGORIES),
    },
    "date": {**DATE, "description": "تاریخ خرید/دریافت؛ پیش‌فرض امروز"},
    "currency": CURRENCY,
    "merchant": {"type": "string", "description": "فروشگاه، طرف حساب یا کارفرما"},
    "account": {"type": "string", "description": "کارت/حساب/کیف پول، مثل «ملت ۱۲۳۴» یا «نقد» — فقط ۴ رقم آخر کارت"},
    "items": ITEMS,
    "note": STR,
    "source": {"type": "string", "enum": SOURCES, "description": "منبع داده؛ پیش‌فرض manual"},
    "attachment": {"type": "string", "description": "مسیر عکس/PDF رسید در workspace، مثل inbox/..."},
}


def normalize_currency(value: str | None) -> str:
    code = (value or "IRT").strip()
    return CURRENCY_ALIASES.get(code.upper(), CURRENCY_ALIASES.get(code, code.upper()))


def format_amount(amount: float, currency: str) -> str:
    text = fa_number(amount)
    return f"{text} {CURRENCY_FA.get(currency, currency)}"


def tx_card(rows: list[dict[str, Any]]) -> tuple[str, InlineKeyboardMarkup | None]:
    """Confirmation text and an undo button for transactions that were just saved."""
    ids = [r["id"] for r in rows]
    if len(rows) == 1:
        r = rows[0]
        sign = "➖" if r["kind"] == "expense" else "➕"
        lines = [f"🧾 ثبت شد · #{r['id']}", f"{sign} {format_amount(r['amount'], r['currency'])} — {r['category']}"]
        details = [x for x in (r.get("merchant") and f"🏪 {r['merchant']}",
                               f"📅 {jalali.to_jalali_str(date.fromisoformat(r['date']))}",
                               r.get("account") and f"💳 {r['account']}") if x]
        lines.append(" · ".join(details))
        if r.get("original_currency") == "IRR":
            lines.append(f"(از {fa_number(r['original_amount'])} ریال)")
    else:
        totals: dict[tuple[str, str], float] = {}
        for r in rows:
            totals[(r["kind"], r["currency"])] = totals.get((r["kind"], r["currency"]), 0) + r["amount"]
        lines = [f"🧾 {fa_number(len(rows))} تراکنش ثبت شد · #{ids[0]}…#{ids[-1]}"]
        for (kind, currency), total in totals.items():
            lines.append(f"{'➖ هزینه' if kind == 'expense' else '➕ درآمد'}: {format_amount(total, currency)}")
    data = "tx:undo:" + ",".join(str(i) for i in ids)
    if len(data.encode()) > 64:  # Telegram's callback_data limit
        return "\n".join(lines), None
    label = "↩️ لغو این ثبت" if len(rows) == 1 else "↩️ لغو همه"
    return "\n".join(lines), InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data)]])


def build(ctx: ToolContext) -> list:
    db = ctx.db
    workspace = ctx.settings.workspace_dir

    def prepare(args: dict[str, Any]) -> dict[str, Any]:
        """Validate one transaction and normalise it to the stored row."""
        kind = args.get("kind")
        if kind not in ("expense", "income"):
            raise ValueError("kind باید expense یا income باشد")
        amount = float(args["amount"])
        if amount <= 0:
            raise ValueError("مبلغ باید مثبت باشد")
        category = (args.get("category") or "").strip()
        if not category:
            raise ValueError("category لازم است")
        currency = normalize_currency(args.get("currency"))
        original_amount = original_currency = None
        if currency == "IRR":
            original_amount, original_currency = amount, "IRR"
            amount, currency = amount / 10, "IRT"
        day = jalali.parse_date(args["date"]) if args.get("date") else ctx.now().date()
        if day > ctx.now().date() + timedelta(days=1):
            raise ValueError(f"تاریخ {jalali.to_jalali_str(day)} در آینده است؛ تاریخ را دوباره بررسی کن")
        attachment = args.get("attachment")
        if attachment:
            path = (workspace / attachment).resolve()
            if not path.is_relative_to(workspace) or not path.exists():
                raise ValueError(f"فایل پیوست در workspace پیدا نشد: {attachment}")
            attachment = str(path.relative_to(workspace))
        items = args.get("items")
        source = args.get("source") or "manual"
        if source not in SOURCES:
            raise ValueError(f"source نامعتبر: {source}")
        return {
            "date": day.isoformat(),
            "kind": kind,
            "amount": round(amount, 2),
            "currency": currency,
            "category": category,
            "account": (args.get("account") or "").strip() or None,
            "note": (args.get("note") or "").strip() or None,
            "merchant": (args.get("merchant") or "").strip() or None,
            "items": json.dumps(items, ensure_ascii=False) if items else None,
            "source": source,
            "attachment": attachment,
            "original_amount": original_amount,
            "original_currency": original_currency,
        }

    async def duplicates(row: dict[str, Any]) -> list[dict[str, Any]]:
        """Same day, kind, amount and currency, and the same merchant (or category if no merchant)."""
        sql = (
            "SELECT id, date, amount, currency, category, merchant, note FROM transactions "
            "WHERE date = ? AND kind = ? AND currency = ? AND ABS(amount - ?) < 0.01"
        )
        params: list[Any] = [row["date"], row["kind"], row["currency"], row["amount"]]
        if row["merchant"]:
            sql += " AND (merchant IS NULL OR merchant = ?)"
            params.append(row["merchant"])
        else:
            sql += " AND category = ?"
            params.append(row["category"])
        return await db.fetchall(sql, params)

    async def insert(row: dict[str, Any]) -> dict[str, Any]:
        columns = list(row) + ["created_at"]
        tx_id = await db.execute(
            f"INSERT INTO transactions ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
            [*row.values(), utcnow_iso()],
        )
        return {"id": tx_id, **row}

    async def known_categories() -> set[str]:
        rows = await db.fetchall("SELECT DISTINCT category FROM transactions")
        return {r["category"] for r in rows} | set(EXPENSE_CATEGORIES) | set(INCOME_CATEGORIES)

    async def announce(saved: list[dict[str, Any]]) -> bool:
        """Show a confirmation card with an undo button in the chat."""
        bot = ctx.app.bot
        if bot is None or not saved or not ctx.settings.finance_cards:
            return False
        text, keyboard = tx_card(saved)
        try:
            await bot.send_message(ctx.chat_id, text, reply_markup=keyboard)
            return True
        except Exception:  # noqa: BLE001 - the transaction is saved either way
            log.warning("could not send transaction card", exc_info=True)
            return False

    def summary_of(row: dict[str, Any]) -> dict[str, Any]:
        out = {k: row[k] for k in ("id", "kind", "amount", "currency", "category", "merchant") if row.get(k)}
        out["date_jalali"] = jalali.to_jalali_str(date.fromisoformat(row["date"]))
        if row.get("original_currency"):
            out["converted_from"] = f"{row['original_amount']:g} {row['original_currency']}"
        return out

    @tool(
        "finance_add_transaction",
        "ثبت یک هزینه یا درآمد (از متن، عکس رسید، فاکتور یا پیامک بانکی). مبلغ مثبت است؛ نوع با kind. "
        "ریال را با currency=IRR بده تا خودکار به تومان تبدیل شود. اگر تراکنش مشابهی همان روز ثبت شده باشد "
        "ثبت نمی‌کند و موارد مشابه را برمی‌گرداند؛ فقط اگر کاربر تأیید کرد که تکراری نیست با "
        "allow_duplicate=true دوباره صدا بزن. بعد از ثبت، کارت تأیید با دکمه لغو خودکار برای کاربر ارسال می‌شود.",
        schema({**TX_FIELDS, "allow_duplicate": {"type": "boolean"}}, ["kind", "amount", "category"]),
    )
    @safe
    async def add_transaction(args: dict[str, Any]) -> dict[str, Any]:
        row = prepare(args)
        if not args.get("allow_duplicate"):
            matches = await duplicates(row)
            if matches:
                return ok({
                    "saved": False,
                    "reason": "possible_duplicate",
                    "matches": [summary_of(m) for m in matches],
                    "next": "از کاربر بپرس تکراری است یا نه؛ اگر نه، با allow_duplicate=true دوباره ثبت کن.",
                })
        new_category = row["category"] not in await known_categories()
        saved = await insert(row)
        result = {"saved": True, **summary_of(saved), "card_shown": await announce([saved])}
        if new_category:
            result["note"] = f"دسته جدید «{row['category']}» ساخته شد؛ اگر منظور یکی از دسته‌های موجود بود، اصلاحش کن."
        return ok(result)

    @tool(
        "finance_add_transactions",
        "ثبت چند تراکنش با هم: رسیدی که باید بین چند دسته تقسیم شود، چند پیامک بانکی، یا صورت‌حساب. "
        "تراکنش‌های احتمالاً تکراری رد می‌شوند و در skipped برمی‌گردند (مگر allow_duplicates=true).",
        schema(
            {
                "transactions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 100,
                    "items": {"type": "object", "properties": TX_FIELDS, "required": ["kind", "amount", "category"]},
                },
                "allow_duplicates": {"type": "boolean"},
            },
            ["transactions"],
        ),
    )
    @safe
    async def add_transactions(args: dict[str, Any]) -> dict[str, Any]:
        rows = [prepare(tx) for tx in args["transactions"]]  # validate everything before writing
        saved, skipped = [], []
        for row in rows:
            matches = [] if args.get("allow_duplicates") else await duplicates(row)
            if matches:
                skipped.append({"transaction": summary_of({**row, "id": None}), "matches": [summary_of(m) for m in matches]})
            else:
                saved.append(await insert(row))
        return ok({
            "saved": [summary_of(r) for r in saved],
            "skipped_as_possible_duplicates": skipped,
            "card_shown": await announce(saved),
        })

    @tool(
        "finance_update_transaction",
        "اصلاح یک تراکنش ثبت‌شده (مبلغ، دسته، تاریخ، فروشنده، ...). فقط فیلدهایی را بده که عوض می‌شوند.",
        schema({"id": INT, **{k: v for k, v in TX_FIELDS.items() if k != "source"}}, ["id"]),
    )
    @safe
    async def update_transaction(args: dict[str, Any]) -> dict[str, Any]:
        current = await db.fetchone("SELECT * FROM transactions WHERE id = ?", (args["id"],))
        if current is None:
            raise ValueError(f"تراکنش #{args['id']} پیدا نشد")
        merged = {**current, "date": current["date"]}
        if current.get("items"):
            merged["items"] = json.loads(current["items"])
        for key, value in args.items():
            if key != "id" and value is not None:
                merged[key] = value
        if "attachment" not in args:  # an old receipt may have been cleaned out of inbox/
            merged.pop("attachment", None)
        row = prepare(merged)
        if "attachment" not in args:
            row["attachment"] = current.get("attachment")
        if "amount" not in args and "currency" not in args:  # keep the original Rial figures
            row["original_amount"], row["original_currency"] = current["original_amount"], current["original_currency"]
        row["source"] = current.get("source") or row["source"]
        await db.execute(
            f"UPDATE transactions SET {', '.join(f'{k} = ?' for k in row)} WHERE id = ?",
            [*row.values(), args["id"]],
        )
        return ok({"updated": True, **summary_of({**row, "id": args["id"]})})

    @tool(
        "finance_list_transactions",
        "فهرست و جستجوی تراکنش‌ها با فیلتر تاریخ، دسته، نوع، ارز و متن (فروشنده/یادداشت).",
        schema(
            {
                "start": DATE,
                "end": {**DATE, "description": "شامل همین روز"},
                "category": STR,
                "kind": {"type": "string", "enum": ["expense", "income"]},
                "currency": STR,
                "query": {"type": "string", "description": "جستجو در فروشنده، یادداشت و اقلام"},
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
        if args.get("currency"):
            where.append("currency = ?")
            params.append(normalize_currency(args["currency"]))
        if args.get("query"):
            where.append("(merchant LIKE ? OR note LIKE ? OR items LIKE ?)")
            params += [f"%{args['query']}%"] * 3
        sql = "SELECT * FROM transactions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(int(args.get("limit") or 50))
        rows = await db.fetchall(sql, params)
        for row in rows:
            row["date_jalali"] = jalali.to_jalali_str(jalali.parse_date(row["date"]))
            if row.get("items"):
                row["items"] = json.loads(row["items"])
            row.pop("created_at", None)
            for key in [k for k, v in row.items() if v is None]:
                row.pop(key)
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
        "finance_categories",
        "دسته‌های استاندارد و دسته‌هایی که کاربر تا حالا استفاده کرده (با تعداد). قبل از ساختن دسته جدید ببین.",
        schema({}),
    )
    @safe
    async def categories(args: dict[str, Any]) -> dict[str, Any]:
        used = await db.fetchall(
            "SELECT kind, category, COUNT(*) AS count FROM transactions GROUP BY kind, category ORDER BY count DESC"
        )
        return ok({"standard_expense": EXPENSE_CATEGORIES, "standard_income": INCOME_CATEGORIES, "used": used})

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
        currency = normalize_currency(args.get("currency"))
        limit = float(args["monthly_limit"])
        if currency == "IRR":
            currency, limit = "IRT", limit / 10
        if limit <= 0:
            await db.execute(
                "DELETE FROM budgets WHERE category = ? AND currency = ?",
                (args["category"], currency),
            )
            return ok({"removed": True})
        await db.execute(
            "INSERT INTO budgets (category, currency, monthly_limit) VALUES (?, ?, ?) "
            "ON CONFLICT(category, currency) DO UPDATE SET monthly_limit = excluded.monthly_limit",
            (args["category"], currency, limit),
        )
        return ok({"saved": True})

    @tool(
        "finance_summary",
        "خلاصه مالی یک ماه شمسی: جمع درآمد و هزینه به تفکیک ارز و دسته، فروشنده‌های اصلی، "
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
        top_merchants = await db.fetchall(
            "SELECT merchant, currency, SUM(amount) AS total, COUNT(*) AS count FROM transactions "
            "WHERE kind = 'expense' AND merchant IS NOT NULL AND date >= ? AND date < ? "
            "GROUP BY merchant, currency ORDER BY total DESC LIMIT 5",
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
                "top_merchants": top_merchants,
                "budgets": budget_status,
            }
        )

    return [
        add_transaction, add_transactions, update_transaction, list_transactions,
        delete_transaction, categories, set_budget, summary,
    ]
