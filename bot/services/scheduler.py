"""Every-minute tick: morning boards and auto-Excel (in config TZ)."""

import calendar
import logging
from datetime import datetime, time, timedelta

from aiogram import Bot
from aiogram.types import FSInputFile

from bot import config
from bot.db import admins, sessions, settings, students
from bot.db.admins import Admin
from bot.handlers import board
from bot.services import excel, season

log = logging.getLogger(__name__)


async def tick(bot: Bot) -> None:
    now = datetime.now(config.TZ)
    if not season.is_school_season(now.date()):
        return
    if now.weekday() >= 5:
        return
    today = now.date().isoformat()
    for admin in await admins.all():
        try:
            st = await settings.get(admin.telegram_id)
            if (
                now.time() >= _parse_hm(st.morning_time)
                and not await sessions.get(admin.telegram_id, today)
                and await students.count_active(admin.school_id, admin.class_name)
            ):
                await board.send_board(bot, admin, now.date())
            if (
                st.excel_enabled
                and st.excel_last_sent != today
                and now.time() >= _parse_hm(st.excel_time)
                and _is_report_day(now, st.excel_day)
            ):
                await _send_report(bot, admin, now)
        except Exception:
            log.exception("tick failed for admin %s", admin.telegram_id)


def _parse_hm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def _is_report_day(now: datetime, excel_day: str) -> bool:
    if excel_day == "last":
        return (now + timedelta(days=1)).month != now.month
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day == min(int(excel_day), last_day)


async def _send_report(bot: Bot, admin: Admin, now: datetime) -> None:
    path = await excel.build_report(admin, now.year, now.month)
    if path is None:
        return
    month = excel.MONTH_NAMES[now.month - 1].lower()
    try:
        await bot.send_document(
            admin.telegram_id,
            FSInputFile(path),
            caption=f"📊 Питание {admin.class_name} за {month} {now.year}",
        )
    finally:
        path.unlink(missing_ok=True)
    await settings.update(admin.telegram_id, excel_last_sent=now.date().isoformat())
