"""Настройки админа: время утренней рассылки и авто-Excel."""

from dataclasses import dataclass

from bot.db import core


@dataclass(slots=True)
class Settings:
    morning_time: str
    excel_enabled: bool
    excel_day: str  # 'last' или '1'..'31'
    excel_time: str
    excel_last_sent: str | None


_FIELDS = "morning_time, excel_enabled, excel_day, excel_time, excel_last_sent"
_UPDATABLE = frozenset(_FIELDS.split(", "))


async def get(telegram_id: int) -> Settings:
    """Дефолты создаются лениво при первом обращении."""
    async with core.connect() as db:
        await db.execute("INSERT OR IGNORE INTO settings(telegram_id) VALUES (?)", (telegram_id,))
        rows = await db.execute_fetchall(
            f"SELECT {_FIELDS} FROM settings WHERE telegram_id = ?", (telegram_id,)
        )
    r = rows[0]
    return Settings(
        r["morning_time"], bool(r["excel_enabled"]), r["excel_day"], r["excel_time"], r["excel_last_sent"]
    )


async def update(telegram_id: int, **fields: str | bool | None) -> None:
    keys = [k for k in fields if k in _UPDATABLE]
    if not keys:
        return
    sets = ", ".join(f"{k} = ?" for k in keys)
    async with core.connect() as db:
        await db.execute(
            f"UPDATE settings SET {sets} WHERE telegram_id = ?",
            (*[fields[k] for k in keys], telegram_id),
        )
