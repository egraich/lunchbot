"""Админы классов и школы."""

from dataclasses import dataclass

from bot.db import core


@dataclass(slots=True)
class Admin:
    telegram_id: int
    school_id: int
    school_name: str
    class_name: str


_SELECT = """
SELECT a.telegram_id, a.school_id, s.name AS school_name, a.class_name
FROM admins a JOIN schools s ON s.id = a.school_id
"""


async def get(telegram_id: int) -> Admin | None:
    async with core.connect() as db:
        rows = await db.execute_fetchall(_SELECT + "WHERE a.telegram_id = ?", (telegram_id,))
    return Admin(**dict(rows[0])) if rows else None


async def all() -> list[Admin]:
    async with core.connect() as db:
        rows = await db.execute_fetchall(_SELECT + "ORDER BY s.name, a.class_name")
    return [Admin(**dict(r)) for r in rows]


async def add(telegram_id: int, school_name: str, class_name: str, added_by: int) -> bool:
    """Добавить админа (существующего — переназначить на другой класс/школу).

    True — добавлен новый, False — переназначен уже существовавший.
    """
    async with core.connect() as db:
        rows = await db.execute_fetchall("SELECT id FROM schools WHERE name = ?", (school_name,))
        if rows:
            school_id = rows[0]["id"]
        else:
            cursor = await db.execute("INSERT INTO schools(name) VALUES (?)", (school_name,))
            school_id = cursor.lastrowid
        existed = bool(
            await db.execute_fetchall("SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,))
        )
        await db.execute(
            """
            INSERT INTO admins(telegram_id, school_id, class_name, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                school_id = excluded.school_id,
                class_name = excluded.class_name,
                added_by = excluded.added_by
            """,
            (telegram_id, school_id, class_name, added_by),
        )
    return not existed


async def delete(telegram_id: int) -> bool:
    async with core.connect() as db:
        cursor = await db.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
    return cursor.rowcount > 0


async def all_schools() -> list[tuple[int, str]]:
    async with core.connect() as db:
        rows = await db.execute_fetchall("SELECT id, name FROM schools ORDER BY name")
    return [(r["id"], r["name"]) for r in rows]


async def get_school_name(school_id: int) -> str | None:
    async with core.connect() as db:
        rows = await db.execute_fetchall("SELECT name FROM schools WHERE id = ?", (school_id,))
    return rows[0]["name"] if rows else None


async def schools_overview() -> list:
    """Школы с классами и числом админов — для /schools."""
    async with core.connect() as db:
        return await db.execute_fetchall(
            """
            SELECT s.name AS school,
                   COUNT(a.telegram_id) AS n,
                   COALESCE(GROUP_CONCAT(a.class_name, ', '), '—') AS classes
            FROM schools s LEFT JOIN admins a ON a.school_id = s.id
            GROUP BY s.id ORDER BY s.name
            """
        )
