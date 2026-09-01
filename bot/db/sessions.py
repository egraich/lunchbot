"""Сессии досок: какое сообщение за какой день у какого админа и в каком статусе."""

from dataclasses import dataclass

from bot.db import core


@dataclass(slots=True)
class BoardSession:
    telegram_id: int
    date: str
    chat_id: int
    message_id: int
    status: str  # open | confirmed | skipped


def _from_row(r) -> BoardSession:
    return BoardSession(r["telegram_id"], r["date"], r["chat_id"], r["message_id"], r["status"])


async def get(telegram_id: int, day: str) -> BoardSession | None:
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT telegram_id, date, chat_id, message_id, status FROM board_sessions"
            " WHERE telegram_id = ? AND date = ?",
            (telegram_id, day),
        )
    return _from_row(rows[0]) if rows else None


async def get_by_message(chat_id: int, message_id: int) -> BoardSession | None:
    """Найти сессию по сообщению — чтобы понять, чья это доска."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT telegram_id, date, chat_id, message_id, status FROM board_sessions"
            " WHERE chat_id = ? AND message_id = ? ORDER BY date DESC LIMIT 1",
            (chat_id, message_id),
        )
    return _from_row(rows[0]) if rows else None


async def upsert(telegram_id: int, day: str, chat_id: int, message_id: int, status: str) -> None:
    async with core.connect() as db:
        await db.execute(
            """
            INSERT INTO board_sessions(telegram_id, date, chat_id, message_id, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id, date) DO UPDATE SET
                chat_id = excluded.chat_id,
                message_id = excluded.message_id,
                status = excluded.status
            """,
            (telegram_id, day, chat_id, message_id, status),
        )


async def set_status(telegram_id: int, day: str, status: str) -> None:
    async with core.connect() as db:
        await db.execute(
            "UPDATE board_sessions SET status = ? WHERE telegram_id = ? AND date = ?",
            (status, telegram_id, day),
        )
