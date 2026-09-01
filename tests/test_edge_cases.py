"""Edge cases: report day logic, month weekday boundaries, name sanitisation."""

from datetime import date, datetime

from bot.services.excel import _safe, month_weekdays
from bot.services.scheduler import _is_report_day


def test_report_day_clamped_to_short_months():
    assert _is_report_day(datetime(2026, 2, 28, 10, 0), "31")
    assert not _is_report_day(datetime(2026, 2, 27, 10, 0), "31")
    assert _is_report_day(datetime(2026, 12, 31, 10, 0), "last")
    assert not _is_report_day(datetime(2026, 12, 30, 10, 0), "last")
    assert _is_report_day(datetime(2026, 9, 15, 10, 0), "15")
    assert not _is_report_day(datetime(2026, 9, 14, 10, 0), "15")


def test_month_weekdays_year_boundary():
    dec = month_weekdays(2026, 12)
    jan = month_weekdays(2027, 1)
    assert dec[-1] == date(2026, 12, 31)
    assert jan[0] == date(2027, 1, 1)


def test_excel_names_sanitized():
    clean = _safe("11/Б:[тест]?*\\")
    for ch in "[]:*?/\\":
        assert ch not in clean
    assert _safe("  ") == "class"


def test_admin_module_imports_ok():
    from bot.db import admins as admins_mod
    assert admins_mod is not None
