FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
# Переменные для неинтерактивной установки
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
# Установка базовых пакетов
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*
# Добавление репозитория для Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa
# Установка Python 3.11 и зависимостей
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
# Установка библиотек CUDA
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
# Создание символических ссылок для CUDA
RUN ln -sf /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/libcuda.so.1
# Создание символической ссылки для python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3
RUN ln -sf /usr/bin/python3.11 /usr/bin/python
# Создание рабочей директории
WORKDIR /app
# Установка pip
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.11
# Создание виртуального окружения
RUN python3.11 -m venv venv
ENV PATH="/app/venv/bin:$PATH"
# Копирование приложения
COPY text-generation-webui /app
# Обновление pip и установка wheel
RUN pip install --upgrade pip wheel setuptools
# Установка PyYAML отдельно
RUN pip install --no-cache-dir pyyaml
# Установка основных зависимостей
RUN pip install --no-cache-dir -r requirements/full/requirements.txt
# Настройка переменных для компиляции
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=86"
ENV FORCE_CMAKE=1
ENV CUDACXX=/usr/local/cuda/bin/nvcc
# Установка llama-cpp-python с CUDA
RUN pip install --upgrade --force-reinstall llama-cpp-python
# Проверка CUDA
RUN python -c "import torch; print(f'PyTorch CUDA available: {torch.cuda.is_available()}')"
# Создание директории для моделей
RUN mkdir -p /app/models
# Открытие портов
EXPOSE 7860
EXPOSE 5000
# Команда запуска с базовыми параметрами
CMD ["python", "server.py", "--model-dir", "./models/saiga", "--model", "saiga_nemo_12b.Q4_K_M.gguf", "--listen", "--api", "--flash-attn", "--threads", "10", "--threads-batch", "14", "--cfg-cache", "--mlock", "--no-mmap"]
