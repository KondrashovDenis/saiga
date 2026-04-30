FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf_cache \
    TRANSFORMERS_CACHE=/models/hf_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3 && \
    python -m pip install --upgrade pip wheel setuptools

WORKDIR /app

COPY requirements.txt /app/
# torch 2.1.2 с cu118 — совместимо с P104-100 (sm_61, Pascal) и driver 535
RUN pip install --index-url https://download.pytorch.org/whl/cu118 \
    torch==2.1.2 torchvision==0.16.2 && \
    pip install -r requirements.txt

COPY server.py /app/

EXPOSE 8000
CMD ["python", "server.py"]
