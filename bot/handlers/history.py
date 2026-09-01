"""📅 Посмотреть записи: месяцы → календарь → день → правка задним числом."""

import calendar
import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from bot.db import records, students
from bot.db.admins import Admin
from bot.handlers import board
from bot.handlers.common import (
    MCB,
    WEEKDAYS_FULL,
    back_row,
    btn,
    edit,
    guard,
    kb,
)
from bot.services import excel
from bot.services.board import EMOJI, STATUS_X
from bot.services.season import VACATION_TEXT, SeasonClosed

router = Router(name="history")
log = logging.getLogger(__name__)


async def history_months_screen(admin: Admin) -> tuple[str, InlineKeyboardMarkup]:
    now = board.today()
    months: list[tuple[int, int]] = []
    year, month = now.year, now.month
    for _ in range(9):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    rows = [
        [
            btn(f"{excel.MONTH_NAMES[m - 1]} {y}", "hist_month", arg=f"{y}-{m:02d}")
            for y, m in months[i:i + 3]
        ]
        for i in range(0, 9, 3)
    ]
    rows.append(back_row())
    return "📅 <b>Записи</b> — за какой месяц посмотреть?", kb(rows)


async def history_month_screen(admin: Admin, year: int, month: int) -> tuple[str, InlineKeyboardMarkup]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    recs = await records.for_month(admin.school_id, admin.class_name, year, month)
    days_with_records = {day for (_sid, day) in recs}

    rows = [[btn(wd, "noop") for wd in WEEKDAYS_FULL]]
    for week in calendar.monthcalendar(year, month):  # сетка пн-вс, как настенный календарь
        row = []
        for day in week:
            if day == 0:  # день соседнего месяца — заглушка, чтобы ряды не ехали
                row.append(btn("▪️", "noop"))
                continue
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            row.append(btn(f"{day:02d} •" if iso in days_with_records else f"{day:02d}", "hist_day", arg=iso))
        rows.append(row)
    rows.append(back_row("history"))
    return f"📅 <b>{excel.MONTH_NAMES[month - 1]} {year}</b> — выбери день (• — есть записи):", kb(rows)


async def history_day_screen(admin: Admin, d: date) -> tuple[str, InlineKeyboardMarkup]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    recs = await records.for_date([s.id for s in sts], d.isoformat())
    weekday = WEEKDAYS_FULL[d.weekday()]
    if recs:
        lines = [f"{EMOJI[recs.get(s.id, STATUS_X)]} {s.name}" for s in sts]
        no_first = sum(1 for v in recs.values() if v == "O")
        with_first = sum(1 for v in recs.values() if v == "O1")
        text = (
            f"📅 <b>{admin.class_name}</b> — {d:%d.%m.%Y} ({weekday})\n\n"
            + "\n".join(lines)
            + f"\n\n🍽 Без первого: <b>{no_first}</b> · С первым: <b>{with_first}</b>"
        )
    else:
        text = (
            f"📅 <b>{admin.class_name}</b> — {d:%d.%m.%Y} ({weekday})\n\n"
            "Записей на этот день нет: день не записывали или все не едят."
        )
    markup = kb([
        [btn("✏️ Открыть доску за этот день", "hist_edit", arg=d.isoformat())],
        [btn("⬅️ К календарю", "hist_month", arg=f"{d.year}-{d.month:02d}"), btn("🏠 Меню", "menu")],
    ])
    return text, markup


@router.callback_query(MCB.filter(F.action == "history"))
async def cb_history(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await history_months_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "hist_month"))
async def cb_hist_month(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    year, month = (int(part) for part in callback_data.arg.split("-"))
    text, markup = await history_month_screen(admin, year, month)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "hist_day"))
async def cb_hist_day(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await history_day_screen(admin, date.fromisoformat(callback_data.arg))
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "hist_edit"))
async def cb_hist_edit(cb: CallbackQuery, callback_data: MCB, bot: Bot) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    if not await students.count_active(admin.school_id, admin.class_name):
        return await cb.answer("Сначала добавь учеников: /management → 🧑‍🎓.", show_alert=True)
    try:
        # майские записи можно править и летом, а вот летние дни не откроются
        await board.send_board(bot, admin, date.fromisoformat(callback_data.arg))
    except SeasonClosed:
        return await cb.answer(VACATION_TEXT, show_alert=True)
    await cb.answer("Доска открыта ниже 👇")
