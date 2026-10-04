"""Freelance work: clients, projects/pipeline, and time tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from claude_agent_sdk import tool

from .. import jalali
from ..context import ToolContext
from ..db import utcnow_iso
from .common import DATE, INT, NUM, STR, ok, safe, schema

PROJECT_STATUS = ["lead", "proposal", "interview", "active", "paused", "done", "lost"]
OPEN_STATUSES = ("lead", "proposal", "interview", "active", "paused")
# Status → timestamp column stamped the first time a project reaches that stage.
STAGE_STAMPS = {"proposal": "proposal_sent_at", "interview": "interviewed_at", "active": "hired_at"}
PROJECT_REF = {"type": "string", "description": "شناسه یا عنوان پروژه"}
CLIENT_FIELDS = ("contact", "source", "currency", "default_rate", "status", "notes")
PROJECT_FIELDS = (
    "title", "status", "billing", "rate", "currency", "estimate_hours", "deadline",
    "next_action", "next_action_date", "notes", "source", "url", "connects",
)


def build(ctx: ToolContext) -> list:
    db = ctx.db

    async def _client_id(name: str) -> int:
        row = await db.fetchone("SELECT id FROM clients WHERE name = ?", (name.strip(),))
        if row:
            return row["id"]
        return await db.execute(
            "INSERT INTO clients (name, created_at) VALUES (?, ?)", (name.strip(), utcnow_iso())
        )

    async def _project(ref: str | int) -> dict[str, Any]:
        ref = str(ref).strip()
        if ref.isdigit():
            row = await db.fetchone("SELECT * FROM projects WHERE id = ?", (int(ref),))
        else:
            rows = await db.fetchall(
                "SELECT * FROM projects WHERE title LIKE ? ORDER BY status IN ('done','lost'), id DESC",
                (f"%{ref}%",),
            )
            row = rows[0] if rows else None
        if not row:
            open_titles = [r["title"] for r in await db.fetchall(
                f"SELECT title FROM projects WHERE status IN {OPEN_STATUSES}"
            )]
            raise ValueError(f"پروژه «{ref}» پیدا نشد. پروژه‌های باز: {open_titles}")
        return row

    async def _running() -> dict[str, Any] | None:
        return await db.fetchone(
            "SELECT t.*, p.title FROM time_entries t JOIN projects p ON p.id = t.project_id "
            "WHERE t.end IS NULL ORDER BY t.id DESC LIMIT 1"
        )

    async def _stop_running(note: str | None = None) -> dict[str, Any] | None:
        running = await _running()
        if not running:
            return None
        end = ctx.now()
        minutes = round((end - datetime.fromisoformat(running["start"])).total_seconds() / 60, 1)
        await db.execute(
            "UPDATE time_entries SET end = ?, minutes = ?, note = COALESCE(?, note) WHERE id = ?",
            (end.isoformat(timespec="seconds"), minutes, note, running["id"]),
        )
        return {"project": running["title"], "minutes": minutes}

    async def _minutes_today() -> float:
        start = ctx.now().replace(hour=0, minute=0, second=0, microsecond=0)
        row = await db.fetchone(
            "SELECT COALESCE(SUM(minutes), 0) AS m FROM time_entries WHERE start >= ? AND minutes IS NOT NULL",
            (start.isoformat(timespec="seconds"),),
        )
        return float(row["m"])

    # --- clients ----------------------------------------------------------

    @tool(
        "client_upsert",
        "ثبت یا به‌روزرسانی مشتری (بر اساس نام). status: lead (مشتری بالقوه)، active، past.",
        schema(
            {
                "name": STR,
                "contact": {"type": "string", "description": "ایمیل/تلگرام/لینکدین"},
                "source": {"type": "string", "description": "از کجا آمده: referral, linkedin, x, upwork, direct"},
                "currency": {"type": "string", "description": "IRT یا USD و ..."},
                "default_rate": {**NUM, "description": "نرخ ساعتی پیش‌فرض"},
                "status": {"type": "string", "enum": ["lead", "active", "past"]},
                "notes": STR,
            },
            ["name"],
        ),
    )
    @safe
    async def client_upsert(args: dict[str, Any]) -> dict[str, Any]:
        client_id = await _client_id(args["name"])
        values = {k: args[k] for k in CLIENT_FIELDS if k in args}
        if "currency" in values:
            values["currency"] = values["currency"].upper()
        if values:
            await db.execute(
                f"UPDATE clients SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
                [*values.values(), client_id],
            )
        return ok({"id": client_id, "saved": True})

    @tool(
        "client_list",
        "فهرست مشتری‌ها با تعداد پروژه‌های باز و درآمد ثبت‌شده از ساعت‌ها.",
        schema({"status": {"type": "string", "enum": ["lead", "active", "past", "all"]}}),
    )
    @safe
    async def client_list(args: dict[str, Any]) -> dict[str, Any]:
        status = args.get("status") or "all"
        sql = (
            "SELECT c.*, "
            f"(SELECT COUNT(*) FROM projects p WHERE p.client_id = c.id AND p.status IN {OPEN_STATUSES}) AS open_projects "
            "FROM clients c"
        )
        params: list[Any] = []
        if status != "all":
            sql += " WHERE c.status = ?"
            params.append(status)
        return ok(await db.fetchall(sql + " ORDER BY c.status, c.name", params))

    # --- projects ---------------------------------------------------------

    @tool(
        "project_upsert",
        "ایجاد پروژه/فرصت جدید (بدون id) یا به‌روزرسانی (با id). برای pipeline فروش هم استفاده "
        "می‌شود: lead (آگهی ذخیره‌شده) → proposal (ارسال شد) → interview → active (استخدام) → done "
        "(یا lost). source مثل upwork، connects = Connects خرج‌شده، url = لینک آگهی. "
        "next_action و next_action_date برای پیگیری (مثلاً «follow-up» سه روز بعد).",
        schema(
            {
                "id": INT,
                "client": {"type": "string", "description": "نام مشتری (اگر نباشد ساخته می‌شود)"},
                "title": STR,
                "status": {"type": "string", "enum": PROJECT_STATUS},
                "billing": {"type": "string", "enum": ["hourly", "fixed"]},
                "rate": {**NUM, "description": "نرخ ساعتی، یا مبلغ کل برای fixed"},
                "currency": STR,
                "estimate_hours": NUM,
                "deadline": DATE,
                "next_action": STR,
                "next_action_date": DATE,
                "notes": STR,
                "source": {"type": "string", "description": "upwork, linkedin, x, referral, direct"},
                "url": STR,
                "connects": INT,
            }
        ),
    )
    @safe
    async def project_upsert(args: dict[str, Any]) -> dict[str, Any]:
        values = {k: args[k] for k in PROJECT_FIELDS if k in args}
        for key in ("deadline", "next_action_date"):
            if values.get(key):
                values[key] = jalali.parse_date(values[key]).isoformat()
        if values.get("currency"):
            values["currency"] = values["currency"].upper()
        if args.get("client"):
            values["client_id"] = await _client_id(args["client"])
        if values.get("source"):
            values["source"] = values["source"].strip().lower()
        now = utcnow_iso()
        stamp = STAGE_STAMPS.get(values.get("status", ""))
        if args.get("id") is None:
            if not values.get("title"):
                raise ValueError("برای پروژه جدید عنوان لازم است")
            if "client_id" in values and "currency" not in values:
                client = await db.fetchone(
                    "SELECT currency, default_rate FROM clients WHERE id = ?", (values["client_id"],)
                )
                values["currency"] = client["currency"]
                if client["default_rate"] and "rate" not in values:
                    values["rate"] = client["default_rate"]
            if stamp:
                values[stamp] = now
            cols = [*values, "created_at", "updated_at"]
            project_id = await db.execute(
                f"INSERT INTO projects ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [*values.values(), now, now],
            )
            return ok({"id": project_id, "created": True})
        if not values:
            raise ValueError("هیچ فیلدی برای تغییر داده نشده")
        await db.execute(
            f"UPDATE projects SET {', '.join(f'{k} = ?' for k in values)}, updated_at = ? WHERE id = ?",
            [*values.values(), now, args["id"]],
        )
        if stamp:  # first time reaching this stage only
            await db.execute(f"UPDATE projects SET {stamp} = ? WHERE id = ? AND {stamp} IS NULL", (now, args["id"]))
        return ok({"id": args["id"], "updated": True})

    @tool(
        "project_list",
        "فهرست پروژه‌ها با ساعت ثبت‌شده، درآمد تقریبی، روزهای مانده تا مهلت و پیگیری‌های سررسیده. "
        "پیش‌فرض: پروژه‌ها و فرصت‌های باز.",
        schema(
            {
                "status": {"type": "string", "enum": [*PROJECT_STATUS, "open", "all"]},
                "client": STR,
            }
        ),
    )
    @safe
    async def project_list(args: dict[str, Any]) -> dict[str, Any]:
        status = args.get("status") or "open"
        where, params = [], []
        if status == "open":
            where.append(f"p.status IN {OPEN_STATUSES}")
        elif status != "all":
            where.append("p.status = ?")
            params.append(status)
        if args.get("client"):
            where.append("c.name LIKE ?")
            params.append(f"%{args['client']}%")
        sql = (
            "SELECT p.*, c.name AS client, "
            "(SELECT COALESCE(SUM(minutes), 0) FROM time_entries t WHERE t.project_id = p.id) AS minutes_logged "
            "FROM projects p LEFT JOIN clients c ON c.id = p.client_id"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = await db.fetchall(sql + " ORDER BY p.deadline IS NULL, p.deadline, p.id", params)
        today = ctx.now().date()
        for row in rows:
            hours = round(row.pop("minutes_logged") / 60, 2)
            row["hours_logged"] = hours
            if row["billing"] == "hourly" and row["rate"]:
                row["earned_estimate"] = round(hours * row["rate"], 2)
            if row["deadline"]:
                deadline = jalali.parse_date(row["deadline"])
                row["deadline_jalali"] = jalali.to_jalali_str(deadline)
                row["days_left"] = (deadline - today).days
            if row["next_action_date"]:
                row["follow_up_due"] = jalali.parse_date(row["next_action_date"]) <= today
            for key in ("created_at", "updated_at"):
                row.pop(key, None)
        return ok(rows)

    # --- time tracking ----------------------------------------------------

    @tool(
        "timer_start",
        "شروع تایمر کار روی یک پروژه (تایمر در حال اجرا قبلی خودکار متوقف می‌شود).",
        schema({"project": PROJECT_REF, "note": STR}, ["project"]),
    )
    @safe
    async def timer_start(args: dict[str, Any]) -> dict[str, Any]:
        project = await _project(args["project"])
        stopped = await _stop_running()
        await db.execute(
            "INSERT INTO time_entries (project_id, start, note) VALUES (?, ?, ?)",
            (project["id"], ctx.now().isoformat(timespec="seconds"), args.get("note")),
        )
        return ok({"started": project["title"], "stopped_previous": stopped})

    @tool(
        "timer_stop",
        "توقف تایمر در حال اجرا و ثبت مدت کار.",
        schema({"note": {"type": "string", "description": "چه کاری انجام شد (اختیاری)"}}),
    )
    @safe
    async def timer_stop(args: dict[str, Any]) -> dict[str, Any]:
        stopped = await _stop_running(args.get("note"))
        if not stopped:
            raise ValueError("تایمری در حال اجرا نیست")
        return ok({**stopped, "minutes_today": await _minutes_today()})

    @tool(
        "timer_status",
        "تایمر در حال اجرا (اگر هست) و جمع دقیقه‌های کار امروز.",
        schema({}),
    )
    @safe
    async def timer_status(args: dict[str, Any]) -> dict[str, Any]:
        running = await _running()
        result: dict[str, Any] = {"running": None, "minutes_today": await _minutes_today()}
        if running:
            elapsed = (ctx.now() - datetime.fromisoformat(running["start"])).total_seconds() / 60
            result["running"] = {"project": running["title"], "elapsed_minutes": round(elapsed, 1)}
        return ok(result)

    @tool(
        "time_log",
        "ثبت دستی زمان کار (وقتی تایمر روشن نبوده)، مثلاً «دیروز ۳ ساعت روی پروژه X».",
        schema(
            {
                "project": PROJECT_REF,
                "minutes": NUM,
                "date": {**DATE, "description": "پیش‌فرض امروز"},
                "note": STR,
            },
            ["project", "minutes"],
        ),
    )
    @safe
    async def time_log(args: dict[str, Any]) -> dict[str, Any]:
        project = await _project(args["project"])
        minutes = float(args["minutes"])
        if not 0 < minutes <= 24 * 60:
            raise ValueError("مدت باید بین ۱ دقیقه و ۲۴ ساعت باشد")
        day = jalali.parse_date(args["date"]) if args.get("date") else ctx.now().date()
        start = datetime(day.year, day.month, day.day, 12, tzinfo=ctx.settings.tz)
        await db.execute(
            "INSERT INTO time_entries (project_id, start, end, minutes, note) VALUES (?, ?, ?, ?, ?)",
            (project["id"], start.isoformat(timespec="seconds"),
             (start + timedelta(minutes=minutes)).isoformat(timespec="seconds"), minutes, args.get("note")),
        )
        return ok({"logged": True, "project": project["title"], "minutes": minutes})

    @tool(
        "time_report",
        "گزارش زمان کار در یک بازه: ساعت و درآمد تقریبی هر پروژه و جمع هر روز. "
        "پیش‌فرض: از شنبه همین هفته تا امروز.",
        schema({"start": DATE, "end": {**DATE, "description": "شامل همین روز"}, "project": PROJECT_REF}),
    )
    @safe
    async def time_report(args: dict[str, Any]) -> dict[str, Any]:
        today = ctx.now().date()
        start = jalali.parse_date(args["start"]) if args.get("start") else jalali.jalali_week_start(today)
        end = jalali.parse_date(args["end"]) if args.get("end") else today
        tz = ctx.settings.tz
        params: list[Any] = [
            datetime(start.year, start.month, start.day, tzinfo=tz).isoformat(timespec="seconds"),
            datetime(end.year, end.month, end.day, tzinfo=tz).replace(hour=23, minute=59, second=59)
            .isoformat(timespec="seconds"),
        ]
        extra = ""
        if args.get("project"):
            extra = " AND p.id = ?"
            params.append((await _project(args["project"]))["id"])
        rows = await db.fetchall(
            "SELECT p.title, p.billing, p.rate, p.currency, substr(t.start, 1, 10) AS day, t.minutes "
            "FROM time_entries t JOIN projects p ON p.id = t.project_id "
            f"WHERE t.minutes IS NOT NULL AND t.start >= ? AND t.start <= ?{extra}",
            params,
        )
        by_project: dict[str, dict[str, Any]] = {}
        by_day: dict[str, float] = {}
        for row in rows:
            entry = by_project.setdefault(
                row["title"], {"minutes": 0.0, "billing": row["billing"], "rate": row["rate"], "currency": row["currency"]}
            )
            entry["minutes"] += row["minutes"]
            by_day[row["day"]] = by_day.get(row["day"], 0.0) + row["minutes"]
        for entry in by_project.values():
            entry["hours"] = round(entry.pop("minutes") / 60, 2)
            if entry["billing"] == "hourly" and entry["rate"]:
                entry["earned_estimate"] = round(entry["hours"] * entry["rate"], 2)
        return ok(
            {
                "range_jalali": [jalali.to_jalali_str(start), jalali.to_jalali_str(end)],
                "total_hours": round(sum(by_day.values()) / 60, 2),
                "projects": by_project,
                "hours_by_day": {
                    jalali.to_jalali_str(jalali.parse_date(day)): round(m / 60, 2) for day, m in sorted(by_day.items())
                },
            }
        )

    @tool(
        "pipeline_stats",
        "آمار قیف فروش در N روز اخیر (پیش‌فرض ۳۰)، اختیاری فقط یک منبع مثل upwork: تعداد پروپوزال، "
        "مصاحبه، استخدام، نرخ تبدیل، Connects خرج‌شده و هزینه هر استخدام.",
        schema({"days": INT, "source": STR}),
    )
    @safe
    async def pipeline_stats(args: dict[str, Any]) -> dict[str, Any]:
        days = int(args.get("days") or 30)
        # proposal_sent_at is stored as UTC ISO text, so compare in UTC.
        since_utc = (ctx.now() - timedelta(days=days)).astimezone(timezone.utc).isoformat(timespec="seconds")
        params: list[Any] = [since_utc]
        extra = ""
        if args.get("source"):
            extra = " AND source = ?"
            params.append(args["source"].strip().lower())
        rows = await db.fetchall(
            "SELECT status, connects, interviewed_at, hired_at FROM projects "
            f"WHERE proposal_sent_at >= ?{extra}",
            params,
        )
        proposals = len(rows)
        interviews = sum(1 for r in rows if r["interviewed_at"] or r["hired_at"])
        hires = sum(1 for r in rows if r["hired_at"])
        connects = sum(r["connects"] or 0 for r in rows)
        pct = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
        return ok(
            {
                "days": days,
                "source": args.get("source") or "all",
                "proposals": proposals,
                "interviews": interviews,
                "hires": hires,
                "interview_rate_pct": pct(interviews, proposals),
                "hire_rate_pct": pct(hires, proposals),
                "connects_spent": connects,
                "connects_usd": round(connects * 0.15, 2),
                "connects_per_hire": round(connects / hires, 1) if hires else None,
                "still_waiting": sum(1 for r in rows if r["status"] == "proposal"),
            }
        )

    return [
        client_upsert, client_list, project_upsert, project_list, pipeline_stats,
        timer_start, timer_stop, timer_status, time_log, time_report,
    ]
