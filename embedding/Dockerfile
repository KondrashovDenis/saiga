# Embedding service: FastAPI + sentence-transformers (multilingual-e5-large) на CPU.
#
# Зачем отдельный контейнер: модель ~2.2 GB и pinned-зависимости тяжёлые
# (torch CPU 200+ MB). Не хочется тянуть это в saiga-web, который должен
# рестартиться быстро. Embedding service деплоится независимо, web и bot
# ходят через HTTP.
#
# Модель лежит в named volume — переживает rebuild контейнера, не качается
# заново при каждом старте.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    SENTENCE_TRANSFORMERS_HOME=/models \
    TRANSFORMERS_OFFLINE=0 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

# Системные зависимости минимальны — только curl для healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Шаг 1: torch CPU-only через прямой URL whl на download.pytorch.org/whl/cpu/.
# Через --index-url / --extra-index-url pip не находит +cpu wheels на новых
# raw-индексах pytorch.org (no top-level metadata). Direct URL — единственный
# надёжный способ. Размер ~200 MB вместо ~2.5 GB у GPU-сборки.
RUN pip install --no-cache-dir \
    "torch @ https://download.pytorch.org/whl/cpu/torch-2.5.1%2Bcpu-cp311-cp311-linux_x86_64.whl"

# Шаг 2: остальные зависимости с обычного pypi.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py

# Папка под модели должна существовать и быть writeable юзеру внутри (root по
# умолчанию в slim — ок для нашего case, в /models смонтируем named volume).
RUN mkdir -p /models && chmod 777 /models

EXPOSE 8000

# uvicorn без --workers: модель грузится в память один раз. Если включить
# многих воркеров — каждый загрузит свою копию (~2.2 GB × N), это нам не нужно.
# Параллельность по запросам — за счёт async-эндпоинтов и ThreadPoolExecutor
# для CPU-bound encode (см. app.py).
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
