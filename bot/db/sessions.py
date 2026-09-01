"""Board sessions: which message belongs to which admin and day, and its status."""

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
    """Return the session for an admin on a specific day, or None."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT telegram_id, date, chat_id, message_id, status FROM board_sessions"
            " WHERE telegram_id = $1 AND date = $2",
            telegram_id,
            day,
        )
    return _from_row(rows[0]) if rows else None


async def get_by_message(chat_id: int, message_id: int) -> BoardSession | None:
    """Find the session by message id to attribute a callback to its board."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT telegram_id, date, chat_id, message_id, status FROM board_sessions"
            " WHERE chat_id = $1 AND message_id = $2 ORDER BY date DESC LIMIT 1",
            chat_id,
            message_id,
        )
    return _from_row(rows[0]) if rows else None


async def upsert(
    telegram_id: int, day: str, chat_id: int, message_id: int, status: str
) -> None:
    """Create or update a board session row."""
    async with core.connect() as db:
        await db.execute(
            """
            INSERT INTO board_sessions(telegram_id, date, chat_id, message_id, status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT(telegram_id, date) DO UPDATE SET
                chat_id = excluded.chat_id,
                message_id = excluded.message_id,
                status = excluded.status
            """,
            telegram_id,
            day,
            chat_id,
            message_id,
            status,
        )


async def set_status(telegram_id: int, day: str, status: str) -> None:
    """Update the status of an existing board session."""
    async with core.connect() as db:
        await db.execute(
            "UPDATE board_sessions SET status = $1 WHERE telegram_id = $2 AND date = $3",
            status,
            telegram_id,
            day,
        )