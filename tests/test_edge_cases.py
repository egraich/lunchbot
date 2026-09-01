"""Пограничные случаи: переназначение админов, отчёт с удалёнными, короткие месяцы."""

import asyncio
from datetime import date, datetime

from bot import config
from bot.db import admins, core, records, students
from bot.services.excel import _safe, month_weekdays
from bot.services.scheduler import _is_report_day


def test_admin_reassign_and_report_keeps_deleted(tmp_path, monkeypatch):
    async def run():
        monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "edge.db"))
        await core.init_db()

        assert await admins.add(1, "Гимназия", "11-Б", 999) is True
        assert await admins.add(1, "Гимназия", "10-А", 999) is False  # уже был — переназначен

        async with core.connect() as db:
            rows = await db.execute_fetchall("SELECT id FROM schools WHERE name = 'Гимназия'")
        school_id = rows[0]["id"]

        assert await students.add(school_id, "11-Б", "Старик Ф")
        assert await students.add(school_id, "11-Б", "Климович И")
        sts = await students.list_active(school_id, "11-Б")
        old = sts[0]
        await records.replace_day([s.id for s in sts], "2025-12-01", {old.id: "O"})
        await students.deactivate(old.id)

        # из доски удалённый пропал...
        assert [s.name for s in await students.list_active(school_id, "11-Б")] == ["Климович И"]
        # ...а из отчёта за декабрь — нет: он ел 1-го числа
        report = await students.list_for_report(school_id, "11-Б", "2025-12-01", "2025-12-31")
        assert [s.name for s in report] == ["Старик Ф", "Климович И"]

    asyncio.run(run())


def test_report_day_clamped_to_short_months():
    # в феврале нет 31-го — отчёт уходит 28-го, а не «никогда»
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
