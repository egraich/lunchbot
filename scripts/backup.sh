#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="./data/backups"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F-%H%M)

docker exec nest_postgres_container pg_dump -U egraich lunchbot \
    > "$BACKUP_DIR/lunchbot-$STAMP.sql"

find "$BACKUP_DIR" -name "lunchbot-*.sql" -mtime +7 -delete
