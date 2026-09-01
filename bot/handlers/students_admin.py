"""Students: add, reorder, rename, delete."""

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.db import admins, students
from bot.db.admins import Admin
from bot.handlers.common import MCB, MState, back_row, btn, edit, guard, kb

router = Router(name="students_admin")
log = logging.getLogger(__name__)


async def students_screen(admin: Admin) -> tuple[str, InlineKeyboardMarkup]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    listing = "\n".join(f"{i + 1}. {s.name}" for i, s in enumerate(sts)) or "Пока никого нет."
    text = f"🧑‍🎓 <b>Ученики</b> ({len(sts)}):\n{listing}"
    markup = kb([
        [btn("➕ Добавить", "st_add"), btn("↕️ Порядок", "st_order")],
        [btn("✏️ Переименовать", "st_rename"), btn("🗑 Удалить", "st_delete")],
        back_row(),
    ])
    return text, markup


@router.callback_query(MCB.filter(F.action == "students"))
async def cb_students(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await students_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_add"))
async def cb_st_add(cb: CallbackQuery, state: FSMContext) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await state.set_state(MState.add_student)
    await state.update_data(added=[])
    if cb.message is not None:
        prompt = await cb.message.answer(
            "🧑‍🎓 Пришли Фамилию И (например <code>Климович И</code>).\n"
            "Можно несколько подряд — чат останется чистым. Закончишь — жми «Готово».",
            reply_markup=kb([[btn("✅ Готово", "st_add_done")]]),
        )
        await state.update_data(prompt_id=prompt.message_id)
    await cb.answer()


@router.message(StateFilter(MState.add_student), F.text & ~F.text.startswith("/"))
async def on_add_student(message: Message, state: FSMContext) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        await state.clear()
        return
    name = message.text.strip()
    if not 2 <= len(name) <= 40:
        return await message.answer("Слишком коротко/длинно. Пришли как <code>Фамилию И</code>.")
    if not await students.add(admin.school_id, admin.class_name, name):
        return await message.answer(f"«{name}» уже есть в списке 🤨")

    data = await state.get_data()
    added = data.get("added", []) + [name]
    await state.update_data(added=added)
    try:
        await message.delete()
    except Exception:
        pass
    text = f"🧑‍🎓 Добавлено ({len(added)}): {', '.join(added)}\nПришли следующего или жми «Готово»."
    markup = kb([[btn("✅ Готово", "st_add_done")]])
    prompt_id = data.get("prompt_id")
    if prompt_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_id, text=text, reply_markup=markup,
            )
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup)


@router.callback_query(MCB.filter(F.action == "st_add_done"))
async def cb_st_add_done(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await students_screen(admin)
    await edit(cb, text, markup)
    await cb.answer("Готово")


async def order_screen(admin: Admin) -> tuple[str, InlineKeyboardMarkup]:
    sts = await students.list_active(admin.school_id, admin.class_name)
    if len(sts) > 32:
        return (
            "😕 Учеников больше 32 — Telegram не даст столько кнопок в одном сообщении.",
            kb([back_row("students")]),
        )
    rows = [
        [btn("⬆️", "st_move", arg=str(s.id), arg2="up"), btn(s.name, "noop"),
         btn("⬇️", "st_move", arg=str(s.id), arg2="down")]
        for s in sts
    ]
    rows.append(back_row("students"))
    return "↕️ <b>Порядок</b> — он же порядок в утренней доске и в Excel.", kb(rows)


@router.callback_query(MCB.filter(F.action == "st_order"))
async def cb_st_order(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    text, markup = await order_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_move"))
async def cb_st_move(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await students.move(int(callback_data.arg), callback_data.arg2)
    text, markup = await order_screen(admin)
    await edit(cb, text, markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_rename"))
async def cb_st_rename(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    sts = await students.list_active(admin.school_id, admin.class_name)
    rows = [[btn(s.name, "st_pick_rename", arg=str(s.id))] for s in sts]
    rows.append(back_row("students"))
    await edit(cb, "✏️ Кого переименовать?", kb(rows))
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_pick_rename"))
async def cb_st_pick_rename(cb: CallbackQuery, callback_data: MCB, state: FSMContext) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    student = await students.get(int(callback_data.arg))
    if student is None:
        return await cb.answer("Ученик не найден.", show_alert=True)
    await state.set_state(MState.rename)
    await state.update_data(student_id=student.id)
    await edit(cb, f"✏️ Пришли новое имя для <b>{student.name}</b>.\n/cancel — отмена.")
    await cb.answer()


@router.message(StateFilter(MState.rename), F.text & ~F.text.startswith("/"))
async def on_rename(message: Message, state: FSMContext) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        await state.clear()
        return
    data = await state.get_data()
    name = message.text.strip()
    if not 2 <= len(name) <= 40:
        return await message.answer("Слишком коротко/длинно. Пришли как <code>Фамилию И</code>.")
    await students.rename(data["student_id"], name)
    await state.clear()
    text, markup = await students_screen(admin)
    await message.answer(f"✅ Теперь это <b>{name}</b>.\n\n{text}", reply_markup=markup)


@router.callback_query(MCB.filter(F.action == "st_delete"))
async def cb_st_delete(cb: CallbackQuery) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    sts = await students.list_active(admin.school_id, admin.class_name)
    rows = [[btn(s.name, "st_pick_delete", arg=str(s.id))] for s in sts]
    rows.append(back_row("students"))
    await edit(cb, "🗑 Кого удалить? (пропадёт из доски и отчётов, история в базе останется)", kb(rows))
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_pick_delete"))
async def cb_st_pick_delete(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    student = await students.get(int(callback_data.arg))
    if student is None:
        return await cb.answer("Ученик не найден.", show_alert=True)
    markup = kb([[
        btn("🗑 Да, удалить", "st_del_yes", arg=str(student.id)),
        btn("Отмена", "students"),
    ]])
    await edit(cb, f"🗑 Точно удалить <b>{student.name}</b>?", markup)
    await cb.answer()


@router.callback_query(MCB.filter(F.action == "st_del_yes"))
async def cb_st_del_yes(cb: CallbackQuery, callback_data: MCB) -> None:
    admin = await guard(cb)
    if admin is None:
        return
    await students.deactivate(int(callback_data.arg))
    text, markup = await students_screen(admin)
    await edit(cb, text, markup)
    await cb.answer("Удалён")
