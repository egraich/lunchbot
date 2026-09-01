"""Meal records: who ate what on which day."""

from bot.db import core


async def for_date(student_ids: list[int], day: str) -> dict[int, str]:
    """Return a dict of student_id -> status for given students on a specific day."""
    if not student_ids:
        return {}
    marks = ",".join(f"${i+2}" for i in range(len(student_ids)))
    async with core.connect() as db:
        rows = await db.fetch(
            f"SELECT student_id, status FROM records WHERE date = $1 AND student_id IN ({marks})",
            day,
            *student_ids,
        )
    return {r["student_id"]: r["status"] for r in rows}


async def for_day_class(school_id: int, class_name: str, day: str) -> dict[int, str]:
    """Return all records for a class on a day, including deleted students (for aggregates)."""
    async with core.connect() as db:
        rows = await db.fetch(
            """
            SELECT r.student_id, r.status
            FROM records r JOIN students s ON s.id = r.student_id
            WHERE s.school_id = $1 AND s.class_name = $2 AND r.date = $3
            """,
            school_id,
            class_name,
            day,
        )
    return {r["student_id"]: r["status"] for r in rows}


async def for_month(
    school_id: int, class_name: str, year: int, month: int
) -> dict[tuple[int, str], str]:
    """Return all records for a class in a given year-month as (student_id, date) -> status."""
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-31"
    async with core.connect() as db:
        rows = await db.fetch(
            """
            SELECT r.student_id, r.date, r.status
            FROM records r JOIN students s ON s.id = r.student_id
            WHERE s.school_id = $1 AND s.class_name = $2 AND r.date BETWEEN $3 AND $4
            """,
            school_id,
            class_name,
            start,
            end,
        )
    return {(r["student_id"], r["date"]): r["status"] for r in rows}


async def replace_day(student_ids: list[int], day: str, statuses: dict[int, str]) -> None:
    """Replace all records for the day: delete old entries and insert the new set."""
    if not student_ids:
        return
    marks = ",".join(f"${i+2}" for i in range(len(student_ids)))
    async with core.connect() as db:
        await db.execute(
            f"DELETE FROM records WHERE date = $1 AND student_id IN ({marks})",
            day,
            *student_ids,
        )
        await db.executemany(
            "INSERT INTO records(student_id, date, status) VALUES ($1, $2, $3)",
            [(sid, day, status) for sid, status in statuses.items()],
        )