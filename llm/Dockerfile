# Saiga LLM image: text-generation-webui (submodule, pinned commit) + llama-cpp-python с CUDA.
# Build context = llm/, поэтому submodule доступен как ./text-generation-webui/.
#
# Apply overlay (config.yaml для модели) поверх submodule перед установкой —
# так апгрейд апстрима сохраняет наши настройки.
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ─────────── Базовые пакеты ───────────
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository ppa:deadsnakes/ppa

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3.11-distutils \
    build-essential \
    git \
    cmake \
    wget \
    curl \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ─────────── CUDA env ───────────
# ВАЖНО: НЕ создавать симлинк на /usr/local/cuda/lib64/stubs/libcuda.so —
# в рантайме nvidia-container-toolkit пробрасывает реальный libcuda.so.1
# с хоста, и stub-симлинк перекрывает его, ломая GPU-инференс.
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# ─────────── Python ───────────
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

RUN curl https://bootstrap.pypa.io/get-pip.py | python3.11

RUN python3.11 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# ─────────── text-generation-webui (submodule) + overlay ───────────
COPY text-generation-webui /app
# Overlay (наш config.yaml) поверх. Если в overlay нет файла — пропустится.
COPY overlays/text-generation-webui/ /app/

RUN pip install --upgrade pip wheel setuptools
RUN pip install --no-cache-dir pyyaml
RUN pip install --no-cache-dir -r requirements/full/requirements.txt

# ─────────── llama-cpp-python с CUDA ───────────
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=86"
ENV FORCE_CMAKE=1
ENV CUDACXX=/usr/local/cuda/bin/nvcc
RUN pip install --upgrade --force-reinstall llama-cpp-python

# ─────────── Sanity ───────────
RUN python -c "import torch; print(f'PyTorch CUDA available: {torch.cuda.is_available()}')"

RUN mkdir -p /app/models

EXPOSE 7860 5000

CMD ["python", "server.py", \
     "--model-dir", "./models/saiga", \
     "--model", "saiga_nemo_12b.Q4_K_M.gguf", \
     "--listen", "--api", \
     "--flash-attn", \
     "--threads", "10", "--threads-batch", "14", \
     "--cfg-cache", "--mlock", "--no-mmap"]
