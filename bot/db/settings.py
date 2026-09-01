"""Admin settings: morning board time and auto-Excel preferences."""

from dataclasses import dataclass

from bot.db import core


@dataclass(slots=True)
class Settings:
    morning_time: str
    excel_enabled: bool
    excel_day: str
    excel_time: str
    excel_last_sent: str | None


_FIELDS = "morning_time, excel_enabled, excel_day, excel_time, excel_last_sent"
_UPDATABLE = frozenset(_FIELDS.split(", "))


async def get(telegram_id: int) -> Settings:
    """Return settings row, creating defaults lazily on first access."""
    async with core.connect() as db:
        await db.execute(
            "INSERT INTO settings(telegram_id) VALUES ($1) ON CONFLICT DO NOTHING",
            telegram_id,
        )
        row = await db.fetchrow(
            f"SELECT {_FIELDS} FROM settings WHERE telegram_id = $1",
            telegram_id,
        )
    r = row
    return Settings(
        r["morning_time"],
        r["excel_enabled"],
        r["excel_day"],
        r["excel_time"],
        r["excel_last_sent"],
    )


async def update(telegram_id: int, **fields: str | bool | None) -> None:
    """Update whitelisted setting keys for an admin."""
    keys = [k for k in fields if k in _UPDATABLE]
    if not keys:
        return
    sets = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(keys))
    async with core.connect() as db:
        await db.execute(
            f"UPDATE settings SET {sets} WHERE telegram_id = $1",
            telegram_id,
            *[fields[k] for k in keys],
        )