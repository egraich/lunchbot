"""Текст «для листка»: агрегация дня, которую дежурный переписывает классруку.

Формат намеренно совпадает с бумажным листком один в один — без даты и
украшений, чтобы копировать и переписывать бездумно.
"""

from bot.services.board import STATUS_O, STATUS_O1


def sheet_text(class_name: str, statuses: dict[int, str]) -> str:
    """statuses — записи дня {student_id: 'O' | 'O1'} (кто не ест — отсутствует)."""
    with_first = sum(1 for v in statuses.values() if v == STATUS_O1)
    without_first = sum(1 for v in statuses.values() if v == STATUS_O)
    return (
        f"{class_name}\n"
        "\n"
        f"Обедов с I : {with_first}\n"
        f"Обедов без I : {without_first}"
    )
