#!/bin/sh
# Web entrypoint: накатывает миграции из shared/migrations/, потом стартует gunicorn.
# Если миграция упадёт — контейнер не запускается (set -e).
set -e

echo "==> Running alembic upgrade head..."
cd /app/shared
alembic upgrade head
cd /app

echo "==> Starting gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    app:app
