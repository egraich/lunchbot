"""School season: September 1 – May 31. Automations sleep in summer."""

from datetime import date


class SeasonClosed(Exception):
    """Raised when trying to open a board outside the school season (and not a superadmin)."""


def is_school_season(d: date) -> bool:
    """Return True for Sep–Dec and Jan–May (school season), False for Jun–Aug (vacation)."""
    return d.month >= 9 or d.month <= 5


VACATION_TEXT = "🏖 <b>Лето!</b> Записи питания откроются <b>1 сентября</b>."
