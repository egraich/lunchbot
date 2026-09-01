"""Ученики класса и правила авто-пропуска по дням недели."""

import sqlite3
from dataclasses import dataclass

from bot.db import core


@dataclass(slots=True)
class Student:
    id: int
    name: str
    position: int


async def list_active(school_id: int, class_name: str) -> list[Student]:
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT id, name, position FROM students"
            " WHERE school_id = ? AND class_name = ? AND is_active = 1"
            " ORDER BY position, id",
            (school_id, class_name),
        )
    return [Student(**dict(r)) for r in rows]


async def list_for_report(school_id: int, class_name: str, start_day: str, end_day: str) -> list[Student]:
    """Активные + удалённые, у которых есть записи за период.

    Ученик, удалённый посреди месяца, должен остаться в Excel за этот месяц.
    """
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT id, name, position FROM students"
            " WHERE school_id = ? AND class_name = ?"
            "   AND (is_active = 1 OR EXISTS ("
            "       SELECT 1 FROM records r"
            "       WHERE r.student_id = students.id AND r.date BETWEEN ? AND ?))"
            " ORDER BY position, id",
            (school_id, class_name, start_day, end_day),
        )
    return [Student(**dict(r)) for r in rows]


async def count_active(school_id: int, class_name: str) -> int:
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM students"
            " WHERE school_id = ? AND class_name = ? AND is_active = 1",
            (school_id, class_name),
        )
    return rows[0]["n"]


async def get(student_id: int) -> Student | None:
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT id, name, position FROM students WHERE id = ?", (student_id,)
        )
    return Student(**dict(rows[0])) if rows else None


async def add(school_id: int, class_name: str, name: str) -> bool:
    """Добавить в конец списка. False — если такой уже есть."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next FROM students"
            " WHERE school_id = ? AND class_name = ?",
            (school_id, class_name),
        )
        try:
            await db.execute(
                "INSERT INTO students(school_id, class_name, name, position) VALUES (?, ?, ?, ?)",
                (school_id, class_name, name, rows[0]["next"]),
            )
        except sqlite3.IntegrityError:
            return False
    return True


async def rename(student_id: int, name: str) -> None:
    async with core.connect() as db:
        await db.execute("UPDATE students SET name = ? WHERE id = ?", (name, student_id))


async def deactivate(student_id: int) -> None:
    """Мягкое удаление: пропадает из доски и отчётов, история в базе остаётся."""
    async with core.connect() as db:
        await db.execute("UPDATE students SET is_active = 0 WHERE id = ?", (student_id,))


async def move(student_id: int, direction: str) -> None:
    """Поменять позицию с соседом сверху/снизу ('up' / 'down')."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT id, position FROM students"
            " WHERE school_id = (SELECT school_id FROM students WHERE id = ?)"
            "   AND class_name = (SELECT class_name FROM students WHERE id = ?)"
            "   AND is_active = 1 ORDER BY position, id",
            (student_id, student_id),
        )
        index = next((i for i, r in enumerate(rows) if r["id"] == student_id), -1)
        other = index - 1 if direction == "up" else index + 1
        if index < 0 or not 0 <= other < len(rows):
            return
        await db.execute(
            "UPDATE students SET position = CASE id WHEN ? THEN ? WHEN ? THEN ? END"
            " WHERE id IN (?, ?)",
            (
                rows[index]["id"], rows[other]["position"],
                rows[other]["id"], rows[index]["position"],
                rows[index]["id"], rows[other]["id"],
            ),
        )


async def auto_skip_ids(school_id: int, class_name: str, weekday: int) -> set[int]:
    """Кого в этот день недели автоматически зажимать на ❌."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT a.student_id AS sid FROM auto_skip a"
            " JOIN students s ON s.id = a.student_id"
            " WHERE s.school_id = ? AND s.class_name = ? AND a.weekday = ? AND s.is_active = 1",
            (school_id, class_name, weekday),
        )
    return {r["sid"] for r in rows}


async def auto_skip_toggle(student_id: int, weekday: int) -> bool:
    """Переключить правило. True — авто-пропуск теперь включён."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            "SELECT 1 FROM auto_skip WHERE student_id = ? AND weekday = ?", (student_id, weekday)
        )
        if rows:
            await db.execute(
                "DELETE FROM auto_skip WHERE student_id = ? AND weekday = ?", (student_id, weekday)
            )
            return False
        await db.execute(
            "INSERT INTO auto_skip(student_id, weekday) VALUES (?, ?)", (student_id, weekday)
        )
    return True
