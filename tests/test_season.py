"""Границы учебного сезона: 1 сентября — 31 мая."""

from datetime import date

from bot.services.season import is_school_season


def test_season_starts_september_first():
    assert not is_school_season(date(2026, 8, 31))  # ещё каникулы
    assert is_school_season(date(2026, 9, 1))       # первый учебный день


def test_season_ends_may_thirty_first():
    assert is_school_season(date(2027, 5, 31))      # последний учебный день
    assert not is_school_season(date(2027, 6, 1))   # начало каникул


def test_season_crosses_new_year():
    assert is_school_season(date(2026, 12, 31))
    assert is_school_season(date(2027, 1, 5))


def test_season_mid_summer():
    assert not is_school_season(date(2026, 7, 15))
    assert not is_school_season(date(2026, 8, 24))  # сегодня — каникулы
