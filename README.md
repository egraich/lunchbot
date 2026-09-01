# Meal Tracker — Telegram Bot for School Lunch Management

A Telegram bot that helps class monitors manage daily school lunch sign-ups. Every morning it sends an inline-keyboard board per class; at month's end it generates a formatted Excel report ready to forward to the class teacher.

## Features

- **Morning board (Mon–Fri)** — one row per student with `[Name ❌] [🍜] [✅]` buttons; name migrates to the pressed button.
- **Statuses** — ✅ = lunch (`O` in Excel), 🍜 = lunch with soup (`O1`), ❌ = absent (empty cell).
- **`/management`** — morning send time, weekday auto-skip, student list (add/reorder/rename/delete), auto-Excel settings, on-demand monthly report, help.
- **Auto-Excel** — sends a `.xlsx` file per class at the configured day/time; format matches a standard class register.
- **Day summary** — after confirming a board, the bot posts a plain-text aggregate for the class teacher.
- **History** — calendar view of any past month; tap a day to reopen and edit it.
- **School isolation** — superadmins manage multiple schools/classes; class admins see only their own board.
- **Soft-delete** — removed students disappear from boards but stay in reports for months they attended.

## Bot Commands

| Command | Who | What |
|---|---|---|
| `/start` | all | Greeting and help |
| `/today` | admin | Open/reopen today's board |
| `/management` | admin | All settings |
| `/cancel` | admin | Cancel current input |
| `/add` | superadmin | Add admin: school picker |
| `/add <id> <class> <school>` | superadmin | Add admin: one-liner |
| `/schools` | superadmin | Schools, classes, admin counts |
| `/del <id>` | superadmin | Remove admin |
| `/admins` | superadmin | Admin list |

## Quick Start (Local)

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# Linux/Mac: .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill BOT_TOKEN, SUPERADMIN_IDS, DATABASE_URL
.venv/Scripts/python -m bot
```

## Docker

```bash
cp .env.example .env   # fill BOT_TOKEN, SUPERADMIN_IDS, DATABASE_URL
docker compose up -d --build
docker compose logs -f
```

The bot expects a Postgres database reachable at `DATABASE_URL`. The bot container must be on the same Docker network as the Postgres container (e.g. `postgres_net`).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `SUPERADMIN_IDS` | — | Comma-separated Telegram user IDs (superadmins) |
| `TZ` | `Europe/Minsk` | Timezone for all scheduling |
| `DATABASE_URL` | — | Full Postgres connection string |
| `DB_POOL_MIN` | `1` | Minimum pool connections |
| `DB_POOL_MAX` | `5` | Maximum pool connections |

## Project Structure

```
bot/
├── __main__.py        # entry point, dispatcher, scheduler
├── config.py          # .env, TZ, logging
├── db/                # asyncpg repositories
├── handlers/          # aiogram routers (start, board, management, etc.)
└── services/          # board logic, Excel, scheduler, season
tests/                 # pytest unit tests (no DB, no network)
scripts/backup.sh      # pg_dump backup with 7-day rotation
docker-compose.yml     # bot container (uses external Postgres)
Dockerfile
LICENSE
```

## Season

The bot operates only during the school year (September 1 – May 31). Automatic boards and auto-Excel are paused in summer; editing past months and on-demand reports still work.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

Tests cover board keyboard roundtrip, history calendar, Excel weekday layout, season boundaries, and sheet text format — all pure unit tests without database or network access.

Made by [egraich](https://egraich.dev) <3
