#!/bin/sh
# Web entrypoint: накатывает миграции из shared/migrations/, потом стартует gunicorn.
# Если миграция упадёт — контейнер не запускается (set -e).
set -e

echo "==> Running alembic upgrade head..."
cd /app/shared
# Alembic запускается под saiga_migrator (DDL права). Если MIGRATION_DATABASE_URL
# не задан — fallback на DATABASE_URL (back-compat для деплоев до миграции
# прав, не должен использоваться в проде после неё).
DATABASE_URL="${MIGRATION_DATABASE_URL:-$DATABASE_URL}" alembic upgrade head
cd /app

echo "==> Starting gunicorn..."
# gthread воркеры (4 worker × 4 threads = 16 параллельных запросов)
# терпимее к slow клиентам чем sync-воркеры — медленный клиент не блокирует
# воркер целиком, только один тред.
#
# --timeout 30 — короткий таймаут от slow-loris атак. Caddy впереди тоже
# обрезает медленные коннекты (read_timeout 60s в Caddyfile).
# Для /api/llm/generate (LLM думает до минуты) Caddy даёт 60s — достаточно
# для не-стриминговых запросов; долгие генерации в будущем перевести на SSE.
#
# --max-requests 1000 — рестарт воркера каждые 1000 запросов, чтобы не копить
# memory leaks (Werkzeug + PIL могут).
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --worker-class gthread \
    --workers 4 \
    --threads 4 \
    --timeout 30 \
    --graceful-timeout 30 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    app:app
