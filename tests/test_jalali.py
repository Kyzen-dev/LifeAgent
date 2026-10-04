from datetime import date, datetime

import pytest

from lifeagent import jalali


def test_parse_jalali_and_gregorian():
    assert jalali.parse_date("1405/07/12") == date(2026, 10, 4)
    assert jalali.parse_date("۱۴۰۵/۰۷/۱۲") == date(2026, 10, 4)
    assert jalali.parse_date("2026-10-04") == date(2026, 10, 4)
    with pytest.raises(ValueError):
        jalali.parse_date("tomorrow")


def test_parse_datetime(tz):
    dt = jalali.parse_datetime("1405/07/12 18:30", tz)
    assert dt == datetime(2026, 10, 4, 18, 30, tzinfo=tz)


def test_month_range_and_week_start():
    start, end = jalali.jalali_month_range(1405, 7)
    assert start == date(2026, 9, 23) and end == date(2026, 10, 23)
    start, end = jalali.jalali_month_range(1405, 12)
    assert jalali.to_jalali_str(end) == "1406/01/01"
    # 2026-10-04 is a Sunday; the Iranian week started Saturday 2026-10-03.
    assert jalali.jalali_week_start(date(2026, 10, 4)) == date(2026, 10, 3)
    assert jalali.jalali_week_start(date(2026, 10, 3)) == date(2026, 10, 3)


def test_human_fa(tz):
    assert jalali.human_fa(datetime(2026, 10, 4, 9, 30, tzinfo=tz)).startswith("یکشنبه 12 مهر 1405")
