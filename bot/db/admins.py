"""Class admins and schools."""

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
    """Return the admin for a Telegram user id, or None."""
    async with core.connect() as db:
        rows = await db.fetch(_SELECT + "WHERE a.telegram_id = $1", telegram_id)
    return Admin(**dict(rows[0])) if rows else None


async def all() -> list[Admin]:
    """Return all admins across all schools ordered by school then class."""
    async with core.connect() as db:
        rows = await db.fetch(_SELECT + "ORDER BY s.name, a.class_name")
    return [Admin(**dict(r)) for r in rows]


async def add(telegram_id: int, school_name: str, class_name: str, added_by: int) -> bool:
    """Attach an admin to a school/class; reassigns existing. Returns True if newly added."""
    async with core.connect() as db:
        row = await db.fetchrow("SELECT id FROM schools WHERE name = $1", school_name)
        if row:
            school_id = row["id"]
        else:
            school_id = await db.fetchval(
                "INSERT INTO schools(name) VALUES ($1) RETURNING id",
                school_name,
            )
        existed = bool(
            await db.fetchrow("SELECT 1 FROM admins WHERE telegram_id = $1", telegram_id)
        )
        await db.execute(
            """
            INSERT INTO admins(telegram_id, school_id, class_name, added_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT(telegram_id) DO UPDATE SET
                school_id = excluded.school_id,
                class_name = excluded.class_name,
                added_by = excluded.added_by
            """,
            telegram_id,
            school_id,
            class_name,
            added_by,
        )
    return not existed


async def delete(telegram_id: int) -> bool:
    """Remove an admin; returns True if an admin was actually deleted."""
    async with core.connect() as db:
        result = await db.execute("DELETE FROM admins WHERE telegram_id = $1", telegram_id)
    return result.split()[-1] == "1"


async def all_schools() -> list[tuple[int, str]]:
    """Return all known schools ordered by name."""
    async with core.connect() as db:
        rows = await db.fetch("SELECT id, name FROM schools ORDER BY name")
    return [(r["id"], r["name"]) for r in rows]


async def get_school_name(school_id: int) -> str | None:
    """Return a school's name by id, or None."""
    async with core.connect() as db:
        row = await db.fetchrow("SELECT name FROM schools WHERE id = $1", school_id)
    return row["name"] if row else None


async def schools_overview() -> list:
    """Aggregate: school name, admin count, and comma-joined classes — for /schools."""
    async with core.connect() as db:
        return await db.fetch(
            """
            SELECT s.name AS school,
                   COUNT(a.telegram_id) AS n,
                   COALESCE(STRING_AGG(a.class_name, ', '), '—') AS classes
            FROM schools s LEFT JOIN admins a ON a.school_id = s.id
            GROUP BY s.id ORDER BY s.name
            """
        )