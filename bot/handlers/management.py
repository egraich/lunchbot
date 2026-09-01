"""/management: menu, send time, auto-skip, auto-Excel, report, help."""

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

from bot import config
from bot.db import admins, records, sessions, settings, students
from bot.db.admins import Admin
from bot.handlers import board
from bot.handlers.common import (
    MCB,
    MState,
    MORNING_PRESETS,
    REPORT_PRESETS,
    WEEKDAYS,
    back_row,
    btn,
    edit,
    guard,
    kb,
    parse_time,
    time_from_cb,
)
from bot.services import excel
from bot.services.season import VACATION_TEXT, SeasonClosed, is_school_season

router = Router(name="management")
log = logging.getLogger(__name__)


async def _today_line(admin: Admin) -> str:
    d = board.today()
    if not is_school_season(d):
        return "🏖 Лето — записи откроются 1 сентября"
    if d.weekday() >= 5:
        return "🍽 Сегодня выходной — записи нет"
    session = await sessions.get(admin.telegram_id, d.isoformat())
    status = {
        None: "⏳ ещё не приходила",
        "open": "⏳ доска открыта — жду подтверждения",
        "confirmed": "✅ записано",
        "skipped": "🚫 день пропущен",
    }[session.status if session else None]
    return f"🍽 Сегодня: {status}"


async def menu_screen(admin: Admin) -> tuple[str, InlineKeyboardMarkup]:
    st = await settings.get(admin.telegram_id)
    n = await students.count_active(admin.school_id, admin.class_name)
    excel_line = f"📊 Авто-Excel: <b>{'вкл ✅' if st.excel_enabled else 'выкл ❌'}</b>"
    if st.excel_enabled:
        day = "последний день" if st.excel_day == "last" else f"{st.excel_day}-е число"
        excel_line += f" — {day}, {st.excel_time}"

    today_line = await _today_line(admin)
    if n == 0:
        today_line += "\n⚠️ Учеников нет — добавь их, иначе записывать некого"

    text = (
        f"⚙️ <b>Управление</b> — {admin.class_name}, {admin.school_name}\n\n"
        f"{today_line}\n"
        f"⏰ Утренняя рассылка: <b>{st.morning_time}</b>\n"
        f"🧑‍🎓 Учеников: <b>{n}</b>\n"
        f"{excel_line}"
    )
    markup = kb([
        [btn("🍽 Доска на сегодня", "today_board")],
        [btn("⏰ Время рассылки", "time")],
        [btn("🙈 Авто-пропуск", "skip")],
        [btn(f"🧑‍🎓 Ученики ({n})", "students")],
        [btn("📊 Авто-Excel", "excel")],
        [btn("📤 Отчёт сейчас", "report")],
        [btn("📅 Посмотреть записи", "history")],
        [btn("❓ Гайды", "help")],
    ])
    return text, markup


@router.message(Command("management"))
async def cmd_management(message: Message, state: FSMContext) -> None:
    await state.clear()
    admin = await admins.get(message.from_user.id)
    if admin is None:
        return
    text, markup = await menu_screen(admin)
    await message.answer(text, reply_markup=markup)


@router.callback_query(MCB.filter(F.action == "menu"))
async def cb_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await menu_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "today_board"))
async def cb_today_board(cb: CallbackQuery, bot: Bot) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    if not await students.count_active(admin.school_id, admin.class_name):
        return await cb.answer("Сначала добавь учеников: /management → 🧑‍🎓.", show_alert=True)
    try:
        await board.send_board(bot, admin, board.today())
    except SeasonClosed:
        return await cb.answer(VACATION_TEXT, show_alert=True)
    await cb.answer("Доска открыта ниже 👇")


@router.callback_query(MCB.filter(F.action == "noop"))
async def cb_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "time"))
async def cb_time(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    st = await settings.get(admin.telegram_id)
    text = f"⏰ <b>Время утренней рассылки</b> (Минск).\nСейчас: <b>{st.morning_time}</b>"
    markup = kb([
        [btn(t, "time_set", arg=t.replace(":", "")) for t in MORNING_PRESETS[:3]],
        [btn(t, "time_set", arg=t.replace(":", "")) for t in MORNING_PRESETS[3:]],
        [btn("✍️ Своё время", "time_custom")],
        back_row(),
    ])
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "time_set"))
async def cb_time_set(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    value = time_from_cb(callback_data.arg)
    await settings.update(admin.telegram_id, morning_time=value)
    text, markup = await menu_screen(admin)
    await edit(cb, text, markup)
    await cb.answer(f"✅ {value}")


@router.callback_query(MCB.filter(F.action == "time_custom"))
async def cb_time_custom(cb: CallbackQuery, state: FSMContext) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await state.set_state(MState.custom_time)
    await edit(cb, "⏰ Пришли время в формате <code>ЧЧ:ММ</code> (например <code>07:35</code>).\n/cancel — отмена.")
    await cb.answer()


@router.message(StateFilter(MState.custom_time), F.text & ~F.text.startswith("/"))
async def on_custom_time(message: Message, state: FSMContext) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        await state.clear()
        return
    value = parse_time(message.text)
    if value is None:
        return await message.answer("Не похоже на ЧЧ:ММ 🤔 Попробуй ещё раз или /cancel.")
    await settings.update(admin.telegram_id, morning_time=value)
    await state.clear()
    text, markup = await menu_screen(admin)
    await message.answer(f"✅ Время сохранено: <b>{value}</b>\n\n{text}", reply_markup=markup)


async def skip_day_screen(admin: Admin, weekday: int) -> tuple[str, InlineKeyboardMarkup]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    locked = await students.auto_skip_ids(admin.school_id, admin.class_name, weekday)
    rows = [
        [btn(("🚫 " if s.id in locked else "▫️ ") + s.name, "skip_toggle", arg=str(weekday), arg2=str(s.id))]
        for s in sts
    ]
    rows.append(back_row("skip"))
    text = (
        f"🙈 <b>{WEEKDAYS[weekday]}</b> — кого автоматически пропускать:\n\n"
        "🚫 — утром будет зажат на ❌ (без выбора), ▫️ — обычный порядок"
    )
    return text, kb(rows)


@router.callback_query(MCB.filter(F.action == "skip"))
async def cb_skip(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text = (
        "🙈 <b>Авто-пропуск</b>\n\n"
        "Выбери день недели: ученики с правилом будут утром зажаты на ❌, "
        "ряд в доске остаётся на месте, но выбрать 🍜/✅ нельзя."
    )
    markup = kb([
        [btn(WEEKDAYS[w], "skip_day", arg=str(w)) for w in range(5)],
        back_row(),
    ])
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "skip_day"))
async def cb_skip_day(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await skip_day_screen(admin, int(callback_data.arg))
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "skip_toggle"))
async def cb_skip_toggle(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    weekday, sid = int(callback_data.arg), int(callback_data.arg2)
    now_locked = await students.auto_skip_toggle(sid, weekday)
    text, markup = await skip_day_screen(admin, weekday)
    await edit(cb, text, markup)
    await cb.answer("🚫 авто-пропуск" if now_locked else "▫️ убрано")


async def excel_screen(admin: Admin) -> tuple[str, InlineKeyboardMarkup]:
    st = await settings.get(admin.telegram_id)
    day = "последний день" if st.excel_day == "last" else f"{st.excel_day}-е число"
    text = (
        "📊 <b>Авто-Excel</b>\n\n"
        f"Статус: <b>{'вкл ✅' if st.excel_enabled else 'выкл ❌'}</b>\n"
        f"Отправка: <b>{day}</b> в <b>{st.excel_time}</b>\n"
        f"Последняя: {st.excel_last_sent or '—'}\n\n"
        "Отчёт придёт тебе в ЛС — перешлёшь классруку."
    )
    markup = kb([
        [btn("Статус: " + ("выкл ❌" if st.excel_enabled else "вкл ✅"), "excel_toggle")],
        [btn(f"📅 День: {day}", "excel_day")],
        [btn(f"⏰ Время: {st.excel_time}", "excel_time")],
        back_row(),
    ])
    return text, markup


@router.callback_query(MCB.filter(F.action == "excel"))
async def cb_excel(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await excel_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "excel_toggle"))
async def cb_excel_toggle(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    st = await settings.get(admin.telegram_id)
    await settings.update(admin.telegram_id, excel_enabled=not st.excel_enabled)
    text, markup = await excel_screen(admin)
    await edit(cb, text, markup)
    await cb.answer("✅ Включено" if not st.excel_enabled else "❌ Выключено")


@router.callback_query(MCB.filter(F.action == "excel_day"))
async def cb_excel_day(cb: CallbackQuery, state: FSMContext) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await state.set_state(MState.excel_day)
    await edit(cb, "📅 Пришли число месяца (1–31) или слово <code>последний</code>.\n/cancel — отмена.")
    await cb.answer()


@router.message(StateFilter(MState.excel_day), F.text & ~F.text.startswith("/"))
async def on_excel_day(message: Message, state: FSMContext) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        await state.clear()
        return
    raw = message.text.strip().lower()
    if raw in ("последний", "посл", "last"):
        value = "last"
    elif raw.isdigit() and 1 <= int(raw) <= 31:
        value = str(int(raw))
    else:
        return await message.answer("Нужно число 1–31 или слово «последний». Ещё раз?")
    await settings.update(admin.telegram_id, excel_day=value)
    await state.clear()
    text, markup = await excel_screen(admin)
    day = "последний день" if value == "last" else f"{value}-е число"
    await message.answer(f"✅ День отправки: <b>{day}</b>\n\n{text}", reply_markup=markup)


@router.callback_query(MCB.filter(F.action == "excel_time"))
async def cb_excel_time(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    st = await settings.get(admin.telegram_id)
    markup = kb([
        [btn(t, "excel_time_set", arg=t.replace(":", "")) for t in REPORT_PRESETS[:3]],
        [btn(t, "excel_time_set", arg=t.replace(":", "")) for t in REPORT_PRESETS[3:]],
        [btn("✍️ Своё время", "excel_time_custom")],
        back_row("excel"),
    ])
    await edit(cb, f"⏰ <b>Время авто-отчёта</b>. Сейчас: <b>{st.excel_time}</b>", markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "excel_time_set"))
async def cb_excel_time_set(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    value = time_from_cb(callback_data.arg)
    await settings.update(admin.telegram_id, excel_time=value)
    text, markup = await excel_screen(admin)
    await edit(cb, text, markup)
    await cb.answer(f"✅ {value}")


@router.callback_query(MCB.filter(F.action == "excel_time_custom"))
async def cb_excel_time_custom(cb: CallbackQuery, state: FSMContext) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await state.set_state(MState.excel_time)
    await edit(cb, "⏰ Пришли время в формате <code>ЧЧ:ММ</code>.\n/cancel — отмена.")
    await cb.answer()


@router.message(StateFilter(MState.excel_time), F.text & ~F.text.startswith("/"))
async def on_excel_time(message: Message, state: FSMContext) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        await state.clear()
        return
    value = parse_time(message.text)
    if value is None:
        return await message.answer("Не похоже на ЧЧ:ММ 🤔 Попробуй ещё раз или /cancel.")
    await settings.update(admin.telegram_id, excel_time=value)
    await state.clear()
    text, markup = await excel_screen(admin)
    await message.answer(f"✅ Время отчёта: <b>{value}</b>\n\n{text}", reply_markup=markup)


@router.callback_query(MCB.filter(F.action == "report"))
async def cb_report(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    markup = kb([
        [btn("Текущий месяц", "report_gen", arg="cur")],
        [btn("Прошлый месяц", "report_gen", arg="prev")],
        back_row(),
    ])
    await edit(cb, "📤 <b>Отчёт сейчас</b> — за какой месяц собрать xlsx?", markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "report_gen"))
async def cb_report_gen(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None or cb.message is None:
        return
    now = datetime.now(config.TZ)
    if callback_data.arg == "prev":
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    else:
        year, month = now.year, now.month
    path = await excel.build_report(admin, year, month)
    if path is None:
        return await cb.answer("Сначала добавь учеников 🤷", show_alert=True)
    caption = f"📊 Питание {admin.class_name} — {excel.MONTH_NAMES[month - 1].lower()} {year}"
    try:
        await cb.message.answer_document(FSInputFile(path), caption=caption)
    finally:
        path.unlink(missing_ok=True)
    await cb.answer("Готово 📊")


GUIDE = (
    "❓ <b>Гайд</b>\n\n"
    "🍽 <b>Доска на сегодня</b> — кнопка в самом верху /management, команды набирать не надо.\n\n"
    "🍽 <b>Утренняя запись.</b> Каждый будний день в назначенное время бот присылает список "
    "класса. ✅ — обед, 🍜 — обед с первым, ❌ — не ест / нет в школе. Имя переезжает на "
    "нажатую кнопку, повторный клик сбрасывает на ❌. Проверил — «Подтвердить».\n\n"
    "📋 <b>Текст для листка.</b> После «Подтвердить» бот пришлёт отдельным сообщением: "
    "класс + «Обедов с I / без I». Просто перепиши классруке. Кнопка под итогом "
    "пересоздаст текст, если исправишь день.\n\n"
    "❗ «Рестарт» и «Подтвердить» при пустом списке срабатывают со второго нажатия — "
    "защита от случайного тапа, отметки не теряются.\n\n"
    "🚫 <b>Праздник / вас нет в школе.</b> Кнопка «НЕ ЗАПИСЫВАТЬ» — день целиком не "
    "записывается. В субботу и воскресенье бот молчит.\n\n"
    "🏖 <b>Лето.</b> С 1 июня по 31 августа бот спит: доски не приходят и не открываются, "
    "авто-Excel молчит. Записи прошлых учебных месяцев поправить можно и летом.\n\n"
    "🙈 <b>Авто-пропуск.</b> /management → Авто-пропуск: выбери день недели и учеников — "
    "утром они будут зажаты на ❌ без кнопок выбора.\n\n"
    "📊 <b>Авто-Excel.</b> /management → Авто-Excel: включи, выбери день и время — в конце "
    "месяца придёт xlsx ровно в формате для классрука, перешлёшь ему в ЛС.\n\n"
    "📤 <b>Отчёт сейчас.</b> /management → Отчёт сейчас → выбери месяц.\n\n"
    "🔁 <b>Исправить после подтверждения:</b> /today — доска откроется с уже записанными "
    "данными, поправь и подтверди снова.\n\n"
    "📅 <b>Посмотреть записи.</b> /management → Посмотреть записи: месяц → календарь → день, "
    "увидишь, кто как записан. Оттуда же «Открыть доску за этот день» — можно исправить "
    "даже вчерашнее.\n\n"
    "⏰ Время рассылки: /management → Время рассылки.\n"
    "🧑‍🎓 Ученики (добавить/порядок/переименовать/удалить): /management → Ученики."
)


@router.callback_query(MCB.filter(F.action == "help"))
async def cb_help(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await edit(cb, GUIDE, kb([back_row()]))
    await cb.answer()
