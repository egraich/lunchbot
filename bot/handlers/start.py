"""Старт, справка, отмена ввода и текст для незнакомцев."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import config
from bot.db import admins
from bot.db.admins import Admin

router = Router(name="start")

PROMO = (
    "👋 Я — бот, помогающий ученикам Беларуси записывать школьное питание.\n\n"
    "Хочешь сэкономить своё время — пиши @egraich"
)

SUPER_HELLO = (
    "👋 Бот записи питания готов. Ты суперадмин.\n\n"
    "<code>/add</code> — добавить админа (кнопками, по школам)\n"
    "<code>/add 123456789 11-Б Гимназия</code> — одной строкой\n"
    "<code>/schools</code> — школы, классы, админы\n"
    "<code>/admins</code> — все админы\n"
    "<code>/del 123456789</code> — убрать админа"
)


def _hello(admin: Admin | None) -> str:
    if admin is None:
        return PROMO
    return (
        "👋 Бот записи питания готов.\n"
        f"Класс: <b>{admin.class_name}</b>, {admin.school_name}\n\n"
        "Каждый будний день в назначенное время придёт список класса.\n\n"
        "/management — настройки (время, авто-пропуск, Excel)\n"
        "/today — открыть сегодняшнюю доску\n"
        "/cancel — отменить ввод"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None and message.from_user.id in config.SUPERADMIN_IDS:
        return await message.answer(SUPER_HELLO)
    await message.answer(_hello(admin))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    admin = await admins.get(message.from_user.id)
    await message.answer(_hello(admin))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(StateFilter(None), F.chat.type == "private")
async def fallback(message: Message) -> None:
    admin = await admins.get(message.from_user.id)
    if admin is None:
        return await message.answer(PROMO)
    await message.answer("Не понял 🤔 Команды: /management, /today")
