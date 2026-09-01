"""Схема БД и хелпер подключения (aiosqlite)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from bot import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS schools (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    school_id   INTEGER NOT NULL REFERENCES schools(id),
    class_name  TEXT NOT NULL,
    added_by    INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id  INTEGER NOT NULL REFERENCES schools(id),
    class_name TEXT NOT NULL,
    name       TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0,
    is_active  INTEGER NOT NULL DEFAULT 1,
    UNIQUE (school_id, class_name, name)
);

CREATE TABLE IF NOT EXISTS records (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('O', 'O1')),
    PRIMARY KEY (student_id, date)
);

CREATE TABLE IF NOT EXISTS board_sessions (
    telegram_id INTEGER NOT NULL,
    date        TEXT NOT NULL,
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    PRIMARY KEY (telegram_id, date)
);

CREATE TABLE IF NOT EXISTS settings (
    telegram_id     INTEGER PRIMARY KEY,
    morning_time    TEXT NOT NULL DEFAULT '07:40',
    excel_enabled   INTEGER NOT NULL DEFAULT 0,
    excel_day       TEXT NOT NULL DEFAULT 'last',
    excel_time      TEXT NOT NULL DEFAULT '16:00',
    excel_last_sent TEXT
);

CREATE TABLE IF NOT EXISTS auto_skip (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    weekday    INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    PRIMARY KEY (student_id, weekday)
);
"""


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    """Открыть соединение; через async with закоммитит (или откатит) и закроет.

    Схема проверяется на каждом подключении: если файл базы удалили
    на живую, таблицы пересоздаются сами (IF NOT EXISTS — копейки).
    """
    db = await aiosqlite.connect(config.DB_PATH)  # динамически: тесты подменяют путь
    db.row_factory = aiosqlite.Row
    try:
        await db.executescript(SCHEMA)
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def init_db() -> None:
    async with connect() as db:
        await db.execute("PRAGMA journal_mode = WAL")
