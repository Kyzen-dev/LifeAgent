"""Reminders and recurring routines (morning brief, weekly review, ...)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

import jdatetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import prompts
from .context import AppContext
from .db import utcnow_iso

log = logging.getLogger(__name__)

RunPrompt = Callable[[int, str], Awaitable[None]]
WEEKDAYS = ("sat", "sun", "mon", "tue", "wed", "thu", "fri")


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.strip().split(":")
    return int(hour), int(minute)


def reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ انجام شد", callback_data=f"rem:done:{reminder_id}"),
                InlineKeyboardButton("⏰ ۱۰ دقیقه", callback_data=f"rem:snooze10:{reminder_id}"),
                InlineKeyboardButton("⏰ ۱ ساعت", callback_data=f"rem:snooze60:{reminder_id}"),
            ]
        ]
    )


class Scheduler:
    def __init__(self, app: AppContext, run_prompt: RunPrompt):
        self.app = app
        self.run_prompt = run_prompt
        self.tz = app.settings.tz
        self.sched = AsyncIOScheduler(timezone=self.tz)

    async def start(self) -> None:
        self._add_routines()
        for row in await self.app.db.fetchall("SELECT * FROM reminders WHERE active = 1"):
            self.schedule_reminder(row)
        self.sched.start()
        log.info("scheduler started with %d jobs", len(self.sched.get_jobs()))

    def shutdown(self) -> None:
        if self.sched.running:
            self.sched.shutdown(wait=False)

    # --- reminders ------------------------------------------------------

    def schedule_reminder(self, row: dict[str, Any]) -> None:
        run_at = datetime.fromisoformat(row["run_at"]).astimezone(self.tz)
        if row["repeat"] == "none":
            # Fire overdue one-off reminders (e.g. missed during a restart) right away.
            run_at = max(run_at, datetime.now(self.tz) + timedelta(seconds=5))
            trigger = DateTrigger(run_date=run_at, timezone=self.tz)
        elif row["repeat"] == "daily":
            trigger = CronTrigger(hour=run_at.hour, minute=run_at.minute, start_date=run_at, timezone=self.tz)
        else:
            days = row.get("days") or WEEKDAYS[(run_at.weekday() + 2) % 7]
            trigger = CronTrigger(
                day_of_week=days, hour=run_at.hour, minute=run_at.minute, start_date=run_at, timezone=self.tz
            )
        self.sched.add_job(
            self._fire_reminder,
            trigger,
            id=f"reminder:{row['id']}",
            args=[row["id"]],
            replace_existing=True,
            misfire_grace_time=6 * 3600,
            coalesce=True,
        )

    def cancel_reminder(self, reminder_id: int) -> None:
        job = self.sched.get_job(f"reminder:{reminder_id}")
        if job:
            job.remove()

    def next_run(self, reminder_id: int) -> datetime | None:
        job = self.sched.get_job(f"reminder:{reminder_id}")
        return job.next_run_time if job else None

    async def add_reminder(
        self, chat_id: int, text: str, run_at: datetime, repeat: str = "none", days: str | None = None
    ) -> int:
        reminder_id = await self.app.db.execute(
            "INSERT INTO reminders (chat_id, text, run_at, repeat, days, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, text, run_at.isoformat(), repeat, days, utcnow_iso()),
        )
        row = await self.app.db.fetchone("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        self.schedule_reminder(row)
        return reminder_id

    async def snooze(self, reminder_id: int, minutes: int) -> None:
        row = await self.app.db.fetchone("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        if row:
            run_at = datetime.now(self.tz) + timedelta(minutes=minutes)
            await self.add_reminder(row["chat_id"], row["text"], run_at)

    async def _fire_reminder(self, reminder_id: int) -> None:
        row = await self.app.db.fetchone("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        if not row or not row["active"]:
            return
        if row["repeat"] == "none":
            await self.app.db.execute("UPDATE reminders SET active = 0 WHERE id = ?", (reminder_id,))
        await self.app.bot.send_message(
            chat_id=row["chat_id"],
            text=f"⏰ یادآوری\n\n{row['text']}",
            reply_markup=reminder_keyboard(reminder_id),
        )

    # --- routines -------------------------------------------------------

    def _add_routines(self) -> None:
        s = self.app.settings
        chat_id = s.owner_chat_id

        def add(job_id: str, trigger: CronTrigger, prompt: str) -> None:
            self.sched.add_job(
                self.run_prompt,
                trigger,
                id=job_id,
                args=[chat_id, prompt],
                replace_existing=True,
                misfire_grace_time=3600,
                coalesce=True,
            )

        if s.morning_brief_time:
            h, m = _parse_hhmm(s.morning_brief_time)
            add("routine:morning", CronTrigger(hour=h, minute=m, timezone=self.tz), prompts.MORNING_BRIEF)
        if s.evening_checkin_time:
            h, m = _parse_hhmm(s.evening_checkin_time)
            add("routine:evening", CronTrigger(hour=h, minute=m, timezone=self.tz), prompts.EVENING_CHECKIN)
        if s.weekly_review:
            day, hhmm = s.weekly_review.split()
            h, m = _parse_hhmm(hhmm)
            add(
                "routine:weekly",
                CronTrigger(day_of_week=day.lower(), hour=h, minute=m, timezone=self.tz),
                prompts.WEEKLY_REVIEW,
            )
        if s.monthly_report_time:
            h, m = _parse_hhmm(s.monthly_report_time)
            # Jalali months don't map to a cron day, so check daily for "day 1".
            self.sched.add_job(
                self._monthly_check,
                CronTrigger(hour=h, minute=m, timezone=self.tz),
                id="routine:monthly",
                replace_existing=True,
                misfire_grace_time=3600,
            )

    async def _monthly_check(self) -> None:
        today = jdatetime.date.fromgregorian(date=datetime.now(self.tz).date())
        if today.day == 1:
            await self.run_prompt(self.app.settings.owner_chat_id, prompts.MONTHLY_REPORT)
