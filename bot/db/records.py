"""Записи питания: кто ест и что именно, по дням."""

from bot.db import core


async def for_date(student_ids: list[int], day: str) -> dict[int, str]:
    if not student_ids:
        return {}
    marks = ",".join("?" * len(student_ids))
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            f"SELECT student_id, status FROM records WHERE date = ? AND student_id IN ({marks})",
            (day, *student_ids),
        )
    return {r["student_id"]: r["status"] for r in rows}


async def for_day_class(school_id: int, class_name: str, day: str) -> dict[int, str]:
    """Все записи класса за день, включая удалённых учеников — для агрегатов."""
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            """
            SELECT r.student_id, r.status
            FROM records r JOIN students s ON s.id = r.student_id
            WHERE s.school_id = ? AND s.class_name = ? AND r.date = ?
            """,
            (school_id, class_name, day),
        )
    return {r["student_id"]: r["status"] for r in rows}


async def for_month(school_id: int, class_name: str, year: int, month: int) -> dict[tuple[int, str], str]:
    # строковое сравнение дат: '-31' покрывает любой последний день месяца
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-31"
    async with core.connect() as db:
        rows = await db.execute_fetchall(
            """
            SELECT r.student_id, r.date, r.status
            FROM records r JOIN students s ON s.id = r.student_id
            WHERE s.school_id = ? AND s.class_name = ? AND r.date BETWEEN ? AND ?
            """,
            (school_id, class_name, start, end),
        )
    return {(r["student_id"], r["date"]): r["status"] for r in rows}


async def replace_day(student_ids: list[int], day: str, statuses: dict[int, str]) -> None:
    """Перезаписать день целиком: старые записи удаляются, новые вставляются."""
    if not student_ids:
        return
    marks = ",".join("?" * len(student_ids))
    async with core.connect() as db:
        await db.execute(
            f"DELETE FROM records WHERE date = ? AND student_id IN ({marks})",
            (day, *student_ids),
        )
        await db.executemany(
            "INSERT INTO records(student_id, date, status) VALUES (?, ?, ?)",
            [(sid, day, status) for sid, status in statuses.items()],
        )
