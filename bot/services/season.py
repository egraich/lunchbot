"""Учебный сезон: 1 сентября — 31 мая. Летом автоматика спит."""

from datetime import date


class SeasonClosed(Exception):
    """Попытка открыть доску вне учебного сезона (и не суперадмин)."""


def is_school_season(d: date) -> bool:
    """Сентябрь–декабрь и январь–май — сезон, июнь–август — каникулы."""
    return d.month >= 9 or d.month <= 5


VACATION_TEXT = "🏖 <b>Лето!</b> Записи питания откроются <b>1 сентября</b>."
