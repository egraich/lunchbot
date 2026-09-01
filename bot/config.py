"""Config from .env and shared constants."""

import logging
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

SUPERADMIN_IDS: frozenset[int] = frozenset(
    int(raw) for raw in os.getenv("SUPERADMIN_IDS", "").replace(" ", "").split(",") if raw
)

TZ = ZoneInfo(os.getenv("TZ", "Europe/Minsk"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "1"))
DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "5"))

DEFAULT_MORNING_TIME = "07:40"
DEFAULT_EXCEL_TIME = "16:00"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] %(message)s",
    )
    for noisy in ("aiogram.event", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)