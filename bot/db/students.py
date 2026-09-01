"""Students and auto-skip rules by weekday."""

from dataclasses import dataclass

import asyncpg

from bot.db import core


@dataclass(slots=True)
class Student:
    id: int
    name: str
    position: int


async def list_active(school_id: int, class_name: str) -> list[Student]:
    """Return active students of a class ordered by position."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT id, name, position FROM students"
            " WHERE school_id = $1 AND class_name = $2 AND is_active = TRUE"
            " ORDER BY position, id",
            school_id,
            class_name,
        )
    return [Student(**dict(r)) for r in rows]


async def list_for_report(school_id: int, class_name: str, start_day: str, end_day: str) -> list[Student]:
    """Return active students plus deleted ones with records in the date range for Excel export."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT id, name, position FROM students"
            " WHERE school_id = $1 AND class_name = $2"
            "   AND (is_active = TRUE OR EXISTS ("
            "       SELECT 1 FROM records r"
            "       WHERE r.student_id = students.id AND r.date BETWEEN $3 AND $4))"
            " ORDER BY position, id",
            school_id,
            class_name,
            start_day,
            end_day,
        )
    return [Student(**dict(r)) for r in rows]


async def count_active(school_id: int, class_name: str) -> int:
    """Return the count of active students in a class."""
    async with core.connect() as db:
        row = await db.fetchrow(
            "SELECT COUNT(*) AS n FROM students"
            " WHERE school_id = $1 AND class_name = $2 AND is_active = TRUE",
            school_id,
            class_name,
        )
    return row["n"]


async def get(student_id: int) -> Student | None:
    """Return a student by their id, or None if not found."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT id, name, position FROM students WHERE id = $1",
            student_id,
        )
    return Student(**dict(rows[0])) if rows else None


async def add(school_id: int, class_name: str, name: str) -> bool:
    """Add student at the end of the list; returns False if name already exists."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next FROM students"
            " WHERE school_id = $1 AND class_name = $2",
            school_id,
            class_name,
        )
        try:
            await db.execute(
                "INSERT INTO students(school_id, class_name, name, position) VALUES ($1, $2, $3, $4)",
                school_id,
                class_name,
                name,
                rows[0]["next"],
            )
        except asyncpg.UniqueViolationError:
            return False
    return True


async def rename(student_id: int, name: str) -> None:
    """Update a student's name."""
    async with core.connect() as db:
        await db.execute("UPDATE students SET name = $1 WHERE id = $2", name, student_id)


async def deactivate(student_id: int) -> None:
    """Soft-delete a student: removes from boards and reports but keeps history."""
    async with core.connect() as db:
        await db.execute(
            "UPDATE students SET is_active = FALSE WHERE id = $1",
            student_id,
        )


async def move(student_id: int, direction: str) -> None:
    """Swap position with a neighbor above ('up') or below ('down')."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT id, position FROM students"
            " WHERE school_id = (SELECT school_id FROM students WHERE id = $1)"
            "   AND class_name = (SELECT class_name FROM students WHERE id = $1)"
            "   AND is_active = TRUE ORDER BY position, id",
            student_id,
        )
        index = next((i for i, r in enumerate(rows) if r["id"] == student_id), -1)
        other = index - 1 if direction == "up" else index + 1
        if index < 0 or not 0 <= other < len(rows):
            return
        await db.execute(
            "UPDATE students SET position = CASE id WHEN $1 THEN $2 WHEN $3 THEN $4 END"
            " WHERE id IN ($5, $6)",
            rows[index]["id"],
            rows[other]["position"],
            rows[other]["id"],
            rows[index]["position"],
            rows[index]["id"],
            rows[other]["id"],
        )


async def auto_skip_ids(school_id: int, class_name: str, weekday: int) -> set[int]:
    """Return IDs of students set to auto-skip on a given weekday."""
    async with core.connect() as db:
        rows = await db.fetch(
            "SELECT a.student_id AS sid FROM auto_skip a"
            " JOIN students s ON s.id = a.student_id"
            " WHERE s.school_id = $1 AND s.class_name = $2 AND a.weekday = $3 AND s.is_active = TRUE",
            school_id,
            class_name,
            weekday,
        )
    return {r["sid"] for r in rows}


async def auto_skip_toggle(student_id: int, weekday: int) -> bool:
    """Toggle the auto-skip rule; returns True if now enabled, False if disabled."""
    async with core.connect() as db:
        exists = await db.fetchrow(
            "SELECT 1 FROM auto_skip WHERE student_id = $1 AND weekday = $2",
            student_id,
            weekday,
        )
        if exists:
            await db.execute(
                "DELETE FROM auto_skip WHERE student_id = $1 AND weekday = $2",
                student_id,
                weekday,
            )
            return False
        await db.execute(
            "INSERT INTO auto_skip(student_id, weekday) VALUES ($1, $2)",
            student_id,
            weekday,
        )
    return True