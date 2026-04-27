FROM python:3.11-slim

# Системные зависимости (libmagic для python-magic, libpq для psycopg2 не нужен — psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Каталог /data сохранился из старой схемы (SQLite). Сейчас не используется,
# оставляю на случай миграции временных файлов / экспортов.
RUN mkdir -p /data && chmod 777 /data

EXPOSE 5000

# Production WSGI server. 4 worker'а — норм для мелкого Flask приложения.
# --access-logfile - выводит логи в stdout (Docker подхватит).
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
