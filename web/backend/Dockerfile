# Используем Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости для обработки файлов
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libmagic-dev \
    file \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы приложения
COPY . .

# Создаем директорию для хранения БД и назначаем права
RUN mkdir -p /data && \
    chown -R nobody:nogroup /data && \
    chmod 777 /data

# Запускаем приложение на Flask
CMD ["python", "app.py"]
