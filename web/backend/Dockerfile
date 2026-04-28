# Build context = repo root (см. web/docker/docker-compose.yml).
# Это нужно потому что shared/ — sibling папка, и должна попасть в образ.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

WORKDIR /app

# 1. shared package (плоская копия + install)
COPY shared/ /app/shared/
RUN pip install --no-cache-dir -e /app/shared

# 2. web requirements
COPY web/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 3. web исходники
COPY web/backend/ /app/

# Каталог /data сохранился из старой схемы (SQLite). Сейчас не используется,
# оставляю на случай миграции временных файлов / экспортов.
RUN mkdir -p /data && chmod 777 /data

EXPOSE 5000

# Entrypoint накатывает миграции (alembic upgrade head), потом стартует gunicorn.
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
