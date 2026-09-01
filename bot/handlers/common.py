"""Общее для хендлеров админки: callback_data, состояния, клавиатурные хелперы."""

import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.db import admins
from bot.db.admins import Admin

MORNING_PRESETS = ("07:00", "07:20", "07:30", "07:40", "07:50", "08:00")
REPORT_PRESETS = ("13:00", "15:00", "16:00", "18:00", "20:00")
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт")
WEEKDAYS_FULL = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class MCB(CallbackData, prefix="mg"):
    action: str
    arg: str = ""
    arg2: str = ""


class MState(StatesGroup):
    custom_time = State()
    add_student = State()
    rename = State()
    excel_day = State()
    excel_time = State()


def btn(text: str, action: str, arg: str = "", arg2: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=MCB(action=action, arg=arg, arg2=arg2).pack())


def kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_row(action: str = "menu") -> list[InlineKeyboardButton]:
    return [btn("⬅️ Назад", action)]


async def guard(cb: CallbackQuery) -> Admin | None:
    admin = await admins.get(cb.from_user.id)
    if admin is None:
        await cb.answer("Нет доступа: ты не админ этого бота.", show_alert=True)
    return admin


async def edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Отредактировать сообщение меню; «not modified» не считаем ошибкой."""
    if cb.message is None:
        return
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


def parse_time(raw: str) -> str | None:
    m = TIME_RE.match(raw.strip())
    if not m:
        return None
    h, minutes = int(m.group(1)), int(m.group(2))
    if h > 23 or minutes > 59:
        return None
    return f"{h:02d}:{minutes:02d}"


def time_from_cb(raw: str) -> str:
    """'0740' из callback_data → '07:40' (двоеточие в callback_data нельзя)."""
    return f"{raw[:2]}:{raw[2:]}"
