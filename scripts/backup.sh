#!/usr/bin/env bash
# Онлайн-бэкап базы Meal Tracker без остановки бота (VACUUM INTO).
# Ставится в cron на VPS, например:
#   30 7 * * * /opt/meal-tracker-bot/scripts/backup.sh >> /var/log/meal-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p data/backups
STAMP=$(date +%F-%H%M)

docker exec -i meal-tracker python - "$STAMP" <<'PY'
import sqlite3
import sys

name = f"/app/data/backups/meal_tracker-{sys.argv[1]}.db"
sqlite3.connect("/app/data/meal_tracker.db").execute(f"VACUUM INTO '{name}'")
print("backup ok:", name)
PY

# храним бэкапы за последние 7 дней
find data/backups -name "meal_tracker-*.db" -mtime +7 -delete
