"""Superadmin commands: /add, /del, /admins, /schools."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import config
from bot.db import admins, settings
from bot.services.commands import setup_commands

router = Router(name="superadmin")
log = logging.getLogger(__name__)


class SACB(CallbackData, prefix="sa"):
    action: str
    arg: str = ""


class SAState(StatesGroup):
    attach_id = State()
    attach_class = State()
    manual = State()


def _is_super_id(user_id: int) -> bool:
    return user_id in config.SUPERADMIN_IDS


def _btn(text: str, action: str, arg: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=SACB(action=action, arg=arg).pack())


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _done_text(is_new: bool, telegram_id: int, class_name: str, school: str) -> str:
    verb = "✅ Добавлен" if is_new else "♻️ Переназначен"
    return (
        f"{verb}: <code>{telegram_id}</code> → {class_name}, {school}.\n"
        "Админ должен нажать /start у бота, иначе бот не сможет написать ему первым."
    )


async def _finish_add(message: Message, telegram_id: int, class_name: str, school: str, is_new: bool) -> None:
    """Create settings and greet the new admin."""
    await settings.get(telegram_id)
    note = ""
    try:
        await message.bot.send_message(
            telegram_id,
            f"👋 Тебя добавили админом класса <b>{class_name}</b> ({school}) в боте записи питания.\n"
            "Дальше: /start → /management → 🧑‍🎓 Ученики.",
        )
    except Exception:
        note = "\n⚠️ Написать ему пока нельзя — пусть нажмёт /start."
    try:
        await setup_commands(message.bot)
    except Exception:
        pass
    await message.answer(_done_text(is_new, telegram_id, class_name, school) + note)


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    if not _is_super_id(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) >= 4:
        try:
            telegram_id = int(parts[1])
        except ValueError:
            return await message.answer("Telegram ID должен быть числом.")
        class_name, school = parts[2].strip(), parts[3].strip()
        is_new = await admins.add(telegram_id, school, class_name, message.from_user.id)
        await _finish_add(message, telegram_id, class_name, school, is_new)
        return

    await state.clear()
    schools = await admins.all_schools()
    rows = [[_btn(name, "school", arg=str(sid))] for sid, name in schools]
    rows.append([_btn("➕ Новая школа (одной строкой)", "manual")])
    await message.answer(
        "👑 <b>Добавление админа</b>\nВыбери школу — или заведи новую:",
        reply_markup=_kb(rows),
    )


@router.callback_query(SACB.filter(F.action == "school"))
async def sa_school(cb: CallbackQuery, callback_data: SACB, state: FSMContext) -> None:
    if not _is_super_id(cb.from_user.id):
        return await cb.answer("Только для суперадминов.", show_alert=True)
    school = await admins.get_school_name(int(callback_data.arg))
    if school is None:
        return await cb.answer("Школа не найдена.", show_alert=True)
    await state.set_state(SAState.attach_id)
    await state.update_data(school_id=int(callback_data.arg), school_name=school)
    if cb.message is not None:
        await cb.message.edit_text(
            f"🏫 Школа: <b>{school}</b>.\nПришли Telegram ID админа (число).\n/cancel — отмена."
        )
    await cb.answer()


@router.message(SAState.attach_id, F.text & ~F.text.startswith("/"))
async def sa_attach_id(message: Message, state: FSMContext) -> None:
    if not _is_super_id(message.from_user.id):
        await state.clear()
        return
    raw = message.text.strip()
    if not raw.isdigit():
        return await message.answer("Нужно число — Telegram ID. Ещё раз, или /cancel.")
    await state.update_data(telegram_id=int(raw))
    await state.set_state(SAState.attach_class)
    await message.answer("Теперь класс этого админа (например <code>11-Б</code>).")


@router.message(SAState.attach_class, F.text & ~F.text.startswith("/"))
async def sa_attach_class(message: Message, state: FSMContext) -> None:
    if not _is_super_id(message.from_user.id):
        await state.clear()
        return
    class_name = message.text.strip()
    if not 1 <= len(class_name) <= 20:
        return await message.answer("Слишком длинно для имени класса. Ещё раз.")
    data = await state.get_data()
    is_new = await admins.add(data["telegram_id"], data["school_name"], class_name, message.from_user.id)
    await state.clear()
    await _finish_add(message, data["telegram_id"], class_name, data["school_name"], is_new)


@router.callback_query(SACB.filter(F.action == "manual"))
async def sa_manual(cb: CallbackQuery, state: FSMContext) -> None:
    if not _is_super_id(cb.from_user.id):
        return await cb.answer("Только для суперадминов.", show_alert=True)
    await state.set_state(SAState.manual)
    if cb.message is not None:
        await cb.message.edit_text(
            "Пришли одной строкой: <code>ID КЛАСС Школа</code>\n"
            "Например: <code>123456789 11-Б Гимназия №2</code>\n/cancel — отмена."
        )
    await cb.answer()


@router.message(SAState.manual, F.text & ~F.text.startswith("/"))
async def sa_manual_add(message: Message, state: FSMContext) -> None:
    if not _is_super_id(message.from_user.id):
        await state.clear()
        return
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3 or not parts[0].isdigit():
        return await message.answer("Формат: <code>ID КЛАСС Школа</code>. Ещё раз, или /cancel.")
    telegram_id = int(parts[0])
    class_name, school = parts[1].strip(), parts[2].strip()
    is_new = await admins.add(telegram_id, school, class_name, message.from_user.id)
    await state.clear()
    await _finish_add(message, telegram_id, class_name, school, is_new)


@router.message(Command("del"))
async def cmd_del(message: Message) -> None:
    if not _is_super_id(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Формат: <code>/del 123456789</code>")
    deleted = await admins.delete(int(parts[1]))
    await message.answer("🗑 Удалён." if deleted else "Такого админа нет.")


@router.message(Command("admins"))
async def cmd_admins(message: Message) -> None:
    if not _is_super_id(message.from_user.id):
        return
    rows = await admins.all()
    if not rows:
        return await message.answer("Админов пока нет. Добавь: <code>/add</code>")
    lines = [f"• <code>{a.telegram_id}</code> — {a.class_name}, {a.school_name}" for a in rows]
    await message.answer("👑 <b>Админы:</b>\n" + "\n".join(lines))


@router.message(Command("schools"))
async def cmd_schools(message: Message) -> None:
    if not _is_super_id(message.from_user.id):
        return
    rows = await admins.schools_overview()
    if not rows:
        return await message.answer("Школ пока нет — добавь первого админа: <code>/add</code>")
    lines = [f"🏫 <b>{r['school']}</b> — {r['n']} адм.: {r['classes']}" for r in rows]
    await message.answer("📚 <b>Школы:</b>\n" + "\n".join(lines))
