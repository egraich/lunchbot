"""Telegram command menu hints (set_my_commands) scoped by role."""

import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from bot import config
from bot.db import admins

log = logging.getLogger(__name__)

BASE = [
    BotCommand(command="start", description="Кто я такой"),
    BotCommand(command="help", description="Помощь"),
]
ADMIN = [
    BotCommand(command="today", description="Доска на сегодня"),
    BotCommand(command="management", description="Настройки"),
    BotCommand(command="cancel", description="Отменить ввод"),
]
SUPER = [
    BotCommand(command="add", description="Добавить админа класса"),
    BotCommand(command="schools", description="Школы и классы"),
    BotCommand(command="admins", description="Список админов"),
    BotCommand(command="del", description="Убрать админа"),
]


async def setup_commands(bot: Bot) -> None:
    """Register command menus: BASE for everyone, ADMIN for class admins, SUPER for superadmins."""
    try:
        await bot.set_my_commands(BASE, scope=BotCommandScopeAllPrivateChats())
    except Exception:
        log.exception("failed to set default commands")
    for admin in await admins.all():
        try:
            await bot.set_my_commands(
                BASE + ADMIN, scope=BotCommandScopeChat(chat_id=admin.telegram_id)
            )
        except Exception:
            pass
    for super_id in config.SUPERADMIN_IDS:
        try:
            await bot.set_my_commands(
                BASE + ADMIN + SUPER, scope=BotCommandScopeChat(chat_id=super_id)
            )
        except Exception:
            pass
