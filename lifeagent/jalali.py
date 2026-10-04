"""Jalali (Solar Hijri) date helpers.

Storage is always Gregorian ISO (YYYY-MM-DD); Jalali is for input and display.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_DATE_RE = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$")
_DATETIME_RE = re.compile(
    r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)

WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
MONTHS_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def normalize_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def _to_gregorian(y: int, m: int, d: int) -> date:
    # Years below 1700 can only be Jalali (current Jalali year is ~1405).
    if y < 1700:
        return jdatetime.date(y, m, d).togregorian()
    return date(y, m, d)


def parse_date(text: str) -> date:
    """Parse 'YYYY-MM-DD' / 'YYYY/MM/DD' in either Jalali or Gregorian."""
    match = _DATE_RE.match(normalize_digits(text))
    if not match:
        raise ValueError(f"تاریخ نامعتبر: {text!r} (فرمت درست: 1405/07/12 یا 2026-10-04)")
    y, m, d = (int(g) for g in match.groups())
    return _to_gregorian(y, m, d)


def parse_datetime(text: str, tz: ZoneInfo) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM' (Jalali or Gregorian) as local time in tz."""
    match = _DATETIME_RE.match(normalize_digits(text))
    if not match:
        raise ValueError(
            f"زمان نامعتبر: {text!r} (فرمت درست: 1405/07/12 18:30 یا 2026-10-04 18:30)"
        )
    y, mo, d, h, mi, s = match.groups()
    day = _to_gregorian(int(y), int(mo), int(d))
    return datetime(day.year, day.month, day.day, int(h), int(mi), int(s or 0), tzinfo=tz)


def to_jalali_str(d: date | datetime, with_time: bool = False) -> str:
    if isinstance(d, datetime):
        jd = jdatetime.datetime.fromgregorian(datetime=d)
        base = f"{jd.year:04d}/{jd.month:02d}/{jd.day:02d}"
        return f"{base} {jd.hour:02d}:{jd.minute:02d}" if with_time else base
    jd = jdatetime.date.fromgregorian(date=d)
    return f"{jd.year:04d}/{jd.month:02d}/{jd.day:02d}"


def human_fa(dt: datetime) -> str:
    """e.g. 'یکشنبه ۱۲ مهر ۱۴۰۵، ساعت 09:30'."""
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    weekday = WEEKDAYS_FA[dt.weekday()]
    return f"{weekday} {jd.day} {MONTHS_FA[jd.month - 1]} {jd.year}، ساعت {dt:%H:%M}"


def jalali_month_range(year: int, month: int) -> tuple[date, date]:
    """Gregorian [start, end) of a Jalali month."""
    start = jdatetime.date(year, month, 1).togregorian()
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    end = jdatetime.date(ny, nm, 1).togregorian()
    return start, end


def current_jalali_month(today: date) -> tuple[int, int]:
    jd = jdatetime.date.fromgregorian(date=today)
    return jd.year, jd.month


def jalali_week_start(today: date) -> date:
    """Most recent Saturday (the Iranian week starts on Saturday)."""
    return today - timedelta(days=(today.weekday() - 5) % 7)


def time_context(now: datetime) -> str:
    """Line prepended to every user turn so the model always knows 'now'."""
    return f"[اکنون: {human_fa(now)} | میلادی {now:%Y-%m-%d %H:%M} | منطقه زمانی {now.tzinfo}]"
