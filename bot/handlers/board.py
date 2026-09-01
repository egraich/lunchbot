"""Утренняя доска: отправка, переключения, подтвердить/пропустить/рестарт."""

import logging
from datetime import date, datetime

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.db import admins, records, sessions, students
from bot.db.admins import Admin
from bot.services.board import (
    EMOJI,
    STATUS_BY_ACTION,
    STATUS_O,
    STATUS_O1,
    STATUS_X,
    MealCB,
    Row,
    build_keyboard,
    build_rows,
    parse_keyboard,
    toggle,
)
from bot.services.season import VACATION_TEXT, SeasonClosed, is_school_season
from bot.services.sheet import sheet_text

router = Router(name="board")
log = logging.getLogger(__name__)


def today() -> date:
    return datetime.now(config.TZ).date()


def board_text(admin: Admin, d: date) -> str:
    return (
        f"🍽 <b>Запись питания</b> — {admin.class_name}, {d:%d.%m}\n"
        "Кто ест — жми ✅ (🍜 — с первым). Кто не ест — оставь ❌."
    )


def _skipped_text(d: date) -> str:
    return f"🚫 <b>Запись не ведётся</b> — {d:%d.%m}.\nПромах — жми «Рестарт»."


def _summary_text(admin: Admin, d: date, rows: list[Row]) -> str:
    lines = [f"✅ <b>Записано</b> — {admin.class_name}, {d:%d.%m}", ""]
    lines += [f"{EMOJI[r.status]} {r.name}" for r in rows]
    lines += ["", "<i>Ошибка? /today — открыть заново.</i>"]
    return "\n".join(lines)


async def class_rows(admin: Admin, d: date) -> list[Row]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    recs = await records.for_date([s.id for s in sts], d.isoformat())
    locked = await students.auto_skip_ids(admin.school_id, admin.class_name, d.weekday())
    return build_rows([(s.id, s.name) for s in sts], recs, locked)


def _restart_only(date_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔄 Рестарт",
            callback_data=MealCB(date=date_str, student_id=0, action="restart").pack(),
        )
    ]])


def _summary_keyboard(date_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📋 Текст для листка",
            callback_data=MealCB(date=date_str, student_id=0, action="sheet").pack(),
        )
    ]])


async def _send_sheet(cb: CallbackQuery, admin: Admin, day: str) -> None:
    """Сообщение «для листка»: класс + обеды с I и без I — переписать бездумно."""
    try:
        recs = await records.for_day_class(admin.school_id, admin.class_name, day)
        await cb.message.answer(sheet_text(admin.class_name, recs))
    except Exception:
        log.exception("failed to send sheet for %s", day)


async def send_board(bot: Bot, admin: Admin, d: date) -> None:
    """Отправить свежую доску и зарегистрировать её как сессию дня.

    Летом доски закрыты для всех, кроме суперадмина (тесты/демо).
    """
    if not is_school_season(d) and admin.telegram_id not in config.SUPERADMIN_IDS:
        raise SeasonClosed()
    day = d.isoformat()
    old = await sessions.get(admin.telegram_id, day)
    if old:
        try:
            await bot.edit_message_text(
                chat_id=old.chat_id, message_id=old.message_id, text="⌛ Эта доска устарела."
            )
        except Exception:
            pass
    msg = await bot.send_message(
        admin.telegram_id,
        board_text(admin, d),
        reply_markup=build_keyboard(day, await class_rows(admin, d)),
    )
    await sessions.upsert(admin.telegram_id, day, msg.chat.id, msg.message_id, "open")


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        return
    d = today()
    if not is_school_season(d) and message.from_user.id not in config.SUPERADMIN_IDS:
        return await message.answer(VACATION_TEXT)
    if d.weekday() >= 5:
        return await message.answer("🛌 Сегодня выходной — записи нет.")
    if not await students.count_active(admin.school_id, admin.class_name):
        return await message.answer("Сначала добавь учеников: /management → 🧑‍🎓 Ученики.")
    await send_board(message.bot, admin, d)


@router.callback_query(MealCB.filter())
async def on_board(cb: CallbackQuery, callback_data: MealCB) -> None:
    if cb.message is None:
        return await cb.answer()
    admin = await admins.get(cb.from_user.id)
    if admin is None:
        return await cb.answer("Ты не админ этого бота.", show_alert=True)

    # безопасность: доска принадлежит конкретной сессии; жать можно только
    # админам ТОГО ЖЕ класса (например, запасному админу)
    session = await sessions.get_by_message(cb.message.chat.id, cb.message.message_id)
    if session is None:
        return await cb.answer("Доска устарела — открой заново: /today", show_alert=True)
    owner = await admins.get(session.telegram_id)
    if owner is None or (owner.school_id, owner.class_name) != (admin.school_id, admin.class_name):
        return await cb.answer("Это доска другого класса 🤨", show_alert=True)

    # доска работает с любой своей датой: и с сегодняшней, и с прошлой
    # (открытие задним числом — через /management → Посмотреть записи)
    try:
        board_date = date.fromisoformat(callback_data.date)
    except ValueError:
        return await cb.answer("Доска устарела.", show_alert=True)

    action = callback_data.action

    # летом записи закрыты; правка прошлых учебных месяцев и листок — можно
    if (action != "sheet" and not is_school_season(board_date)
            and cb.from_user.id not in config.SUPERADMIN_IDS):
        return await cb.answer("🏖 Лето! Записи откроются 1 сентября.", show_alert=True)

    if action in STATUS_BY_ACTION:  # x / O / O1 — клик по кнопке ученика
        try:
            rows = parse_keyboard(cb.message.reply_markup)
        except ValueError:
            return await cb.answer("Доска устарела — открой заново: /today", show_alert=True)
        target = next((r for r in rows if r.student_id == callback_data.student_id), None)
        if target is None:
            return await cb.answer("Ученик не найден — открой заново: /today", show_alert=True)
        if target.locked:
            return await cb.answer("🔒 Авто-пропуск по настройке (/management → 🙈).", show_alert=True)
        rows = toggle(rows, callback_data.student_id, action)
        try:
            await cb.message.edit_reply_markup(reply_markup=build_keyboard(callback_data.date, rows))
        except TelegramBadRequest:
            pass
        return await cb.answer()

    if action in ("restart", "restart_yes"):
        try:
            rows = parse_keyboard(cb.message.reply_markup)
        except ValueError:
            return await cb.answer("Доска устарела — открой заново: /today", show_alert=True)
        if action == "restart" and any(r.status != STATUS_X for r in rows if not r.locked):
            # защита от случайного тапа: первый клик только взводит кнопку,
            # отметки остаются на местах
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=build_keyboard(callback_data.date, rows, arm="restart")
                )
            except TelegramBadRequest:
                pass
            return await cb.answer("Нажми ещё раз — сбросятся ВСЕ отметки")
        try:
            await cb.message.edit_text(
                board_text(admin, board_date),
                reply_markup=build_keyboard(callback_data.date, await class_rows(admin, board_date)),
            )
        except TelegramBadRequest:
            pass
        await sessions.set_status(cb.from_user.id, callback_data.date, "open")
        return await cb.answer("Начали заново 🔄")

    if action == "skip":
        try:
            await cb.message.edit_text(_skipped_text(board_date), reply_markup=_restart_only(callback_data.date))
        except TelegramBadRequest:
            pass
        await sessions.set_status(cb.from_user.id, callback_data.date, "skipped")
        return await cb.answer("День не записываем")

    if action in ("confirm", "confirm_force"):
        try:
            rows = parse_keyboard(cb.message.reply_markup)
        except ValueError:
            return await cb.answer("Доска устарела — открой заново: /today", show_alert=True)
        statuses = {r.student_id: r.status for r in rows if r.status in (STATUS_O, STATUS_O1)}
        if action == "confirm" and not statuses:
            # пустой день подтверждаем дважды — вдруг промахнулись
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=build_keyboard(callback_data.date, rows, arm="confirm")
                )
            except TelegramBadRequest:
                pass
            return await cb.answer("Никто не отмечен ✅/🍜. Ещё раз — запишу день пустым.")
        await records.replace_day([r.student_id for r in rows], callback_data.date, statuses)
        await sessions.set_status(cb.from_user.id, callback_data.date, "confirmed")
        try:
            await cb.message.edit_text(
                _summary_text(admin, board_date, rows),
                reply_markup=_summary_keyboard(callback_data.date),
            )
        except TelegramBadRequest:
            pass
        await _send_sheet(cb, admin, callback_data.date)
        return await cb.answer("Записано ✅")

    if action == "sheet":
        # считаем по записям класса целиком (включая удалённых после еды),
        # чтобы цифры всегда сходились с Excel
        recs = await records.for_day_class(admin.school_id, admin.class_name, callback_data.date)
        await cb.message.answer(sheet_text(admin.class_name, recs))
        return await cb.answer("Готово 📋")

    await cb.answer()
