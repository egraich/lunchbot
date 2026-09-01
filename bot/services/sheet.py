"""Plain-text day summary for the class teacher to copy verbatim."""

from bot.services.board import STATUS_O, STATUS_O1


def sheet_text(class_name: str, statuses: dict[int, str]) -> str:
    """Return a copy-friendly aggregate: class name, lunches with soup count, lunches without."""
    with_first = sum(1 for v in statuses.values() if v == STATUS_O1)
    without_first = sum(1 for v in statuses.values() if v == STATUS_O)
    return (
        f"{class_name}\n"
        "\n"
        f"Обедов с I : {with_first}\n"
        f"Обедов без I : {without_first}"
    )
