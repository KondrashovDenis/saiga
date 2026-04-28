#!/bin/bash
# pg_dump бэкап saiga + vaibkod_cms (обе БД делят saiga-postgres).
# Запускать с homeserver под denciao. Ротация — оставляем последние 7 файлов.
#
# Cron-пример (через `crontab -e`):
#   30 3 * * * /home/denciao/projects/saiga/web/backup.sh >> /home/denciao/projects/saiga/backups/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="/home/denciao/projects/saiga/backups"
KEEP=7
DATE="$(date +%F_%H-%M-%S)"

mkdir -p "$BACKUP_DIR"

# pg_dumpall через docker exec — захватываем обе БД (saiga + vaibkod_cms),
# роли тоже включены (saiga_app, saiga_admin), что упрощает restore.
# Пароль saiga_admin не нужен — внутри контейнера PG доверяет local connections.
docker exec saiga-postgres pg_dumpall -U saiga_admin --clean --if-exists \
    | gzip > "$BACKUP_DIR/saiga_pgdumpall_$DATE.sql.gz"

# Ротация: оставляем самые новые $KEEP штук, остальные удаляем.
ls -1t "$BACKUP_DIR"/saiga_pgdumpall_*.sql.gz 2>/dev/null \
    | tail -n +"$((KEEP + 1))" \
    | xargs -r rm --

LATEST="$BACKUP_DIR/saiga_pgdumpall_$DATE.sql.gz"
SIZE="$(du -h "$LATEST" | cut -f1)"
echo "[$(date -Iseconds)] backup OK: $LATEST ($SIZE)"
