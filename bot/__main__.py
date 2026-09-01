"""Точка входа: инициализация БД, диспетчер, роутеры, планировщик, polling."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config
from bot.db import core
from bot.handlers import (
    board,
    history,
    management,
    start,
    students_admin,
    superadmin,
)
from bot.services import commands
from bot.services.scheduler import tick

log = logging.getLogger(__name__)


async def main() -> None:
    config.setup_logging()
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN пуст — заполни .env (см. .env.example)")
    await core.init_db()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(
        superadmin.router,
        management.router,
        students_admin.router,
        history.router,
        board.router,
        start.router,
    )

    await commands.setup_commands(bot)

    scheduler = AsyncIOScheduler(timezone=config.TZ)
    scheduler.add_job(tick, "interval", minutes=1, args=(bot,), max_instances=1, coalesce=True)
    scheduler.start()

    log.info("bot started")
    try:
        while True:
            try:
                await dp.start_polling(bot)
                break
            except TelegramConflictError:
                # второй экземпляр бота где-то поллит — не падаем, ждём его
                log.warning("409: другой экземпляр бота уже запущен, повтор через 15 с")
                await asyncio.sleep(15)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
