"""Pure morning-board logic: rows, keyboard assembly and parsing.

Board state is entirely encoded in the message reply_markup — parse the current
keyboard, apply a toggle, rebuild. This survives bot restarts and needs no
separate storage.
"""

from dataclasses import dataclass

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

STATUS_X = "x"
STATUS_O = "O"
STATUS_O1 = "O1"

EMOJI = {STATUS_X: "❌", STATUS_O: "✅", STATUS_O1: "🍜"}
ROW_ORDER = (STATUS_X, STATUS_O1, STATUS_O)

ACTION_BY_STATUS = {STATUS_X: "x", STATUS_O: "O", STATUS_O1: "O1"}
STATUS_BY_ACTION = {v: k for k, v in ACTION_BY_STATUS.items()}


class MealCB(CallbackData, prefix="m"):
    date: str
    student_id: int
    action: str


@dataclass(slots=True)
class Row:
    student_id: int
    name: str
    status: str = STATUS_X
    locked: bool = False


def build_rows(
    students: list[tuple[int, str]],
    records: dict[int, str],
    locked: set[int],
) -> list[Row]:
    return [Row(sid, name, records.get(sid, STATUS_X), sid in locked) for sid, name in students]


def build_keyboard(date_str: str, rows: list[Row], *, arm: str | None = None) -> InlineKeyboardMarkup:
    """Build the inline-keyboard board. arm='restart'/'confirm' arms the safety button."""
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text="❌ НЕ ЗАПИСЫВАТЬ ❌",
            callback_data=MealCB(date=date_str, student_id=0, action="skip").pack(),
        )]
    ]
    for r in rows:
        if r.locked:
            keyboard.append([_student_button(date_str, r, STATUS_X)])
            continue
        keyboard.append([_student_button(date_str, r, status) for status in ROW_ORDER])
    if arm == "restart":
        restart = InlineKeyboardButton(
            text="❓ Точно сбросить?",
            callback_data=MealCB(date=date_str, student_id=0, action="restart_yes").pack(),
        )
    else:
        restart = InlineKeyboardButton(
            text="🔄 Рестарт",
            callback_data=MealCB(date=date_str, student_id=0, action="restart").pack(),
        )
    if arm == "confirm":
        confirm = InlineKeyboardButton(
            text="✅ Точно записать пустым?",
            callback_data=MealCB(date=date_str, student_id=0, action="confirm_force").pack(),
        )
    else:
        confirm = InlineKeyboardButton(
            text="Подтвердить ✅",
            callback_data=MealCB(date=date_str, student_id=0, action="confirm").pack(),
        )
    keyboard.append([restart, confirm])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _student_button(date_str: str, row: Row, status: str) -> InlineKeyboardButton:
    label = f"{row.name} {EMOJI[status]}" if status == row.status else EMOJI[status]
    return InlineKeyboardButton(
        text=label,
        callback_data=MealCB(
            date=date_str, student_id=row.student_id, action=ACTION_BY_STATUS[status]
        ).pack(),
    )


def parse_keyboard(markup: InlineKeyboardMarkup | None) -> list[Row]:
    """Restore rows from a reply_markup; raises ValueError if not a meal board."""
    if markup is None:
        raise ValueError("no markup")
    rows: list[Row] = []
    for line in markup.inline_keyboard:
        first = line[0]
        if not first.callback_data or not first.callback_data.startswith("m:"):
            continue
        head = MealCB.unpack(first.callback_data)
        if head.student_id == 0:
            continue
        if len(line) == 1:
            rows.append(Row(head.student_id, _name(first.text), STATUS_X, locked=True))
            continue
        chosen = next((b for b in line if b.text not in EMOJI.values()), first)
        if not chosen.callback_data:
            raise ValueError("button without callback_data")
        cb = MealCB.unpack(chosen.callback_data)
        rows.append(Row(cb.student_id, _name(chosen.text), STATUS_BY_ACTION[cb.action]))
    if not rows:
        raise ValueError("not a meal board")
    return rows


def _name(label: str) -> str:
    return label.rsplit(" ", 1)[0]


def toggle(rows: list[Row], student_id: int, action: str) -> list[Row]:
    """Toggle a student's status; repeated click on the same button resets to X."""
    status = STATUS_BY_ACTION[action]
    for r in rows:
        if r.student_id == student_id and not r.locked:
            r.status = STATUS_X if r.status == status else status
            break
    return rows
