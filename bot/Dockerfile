# Build context = repo root (см. bot/docker-compose.yml).
# shared/ — sibling папка с моделями, должна попасть в образ.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. shared package
COPY shared/ /app/shared/
RUN pip install --no-cache-dir -e /app/shared

# 2. bot requirements
COPY bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 3. bot исходники
COPY bot/src/ /app/

RUN mkdir -p /app/data /app/logs

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
