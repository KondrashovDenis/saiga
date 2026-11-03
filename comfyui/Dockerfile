# ComfyUI for Pascal P104-100 (sm_61) under NVIDIA driver 535: CUDA 11.8 runtime + torch cu118.
# Same base and python layout as ../imagegen (known-good on this GPU).
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    git ca-certificates curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3 && \
    python -m pip install --upgrade pip wheel setuptools

# torch cu118 wheels carry sm_60 SASS, which runs on sm_61 (binary compatible within a major).
RUN python -m pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu118

# ComfyUI pinned to the last commit before COMFY_BEFORE (core nodes only are needed:
# CheckpointLoaderSimple, CLIPTextEncode, ControlNetLoader/ApplyAdvanced, EmptyLatentImage, KSampler, VAEDecode, LoadImage, SaveImage)
ARG COMFY_BEFORE=2025-06-01
RUN git clone https://github.com/comfyanonymous/ComfyUI /app \
    && cd /app \
    && git checkout --quiet "$(git rev-list -n 1 --before="${COMFY_BEFORE}" master)" \
    && git log -1 --format='%h %ci %s' | tee /app/COMFY_COMMIT.txt \
    && python -m pip install -r requirements.txt

# transformers 5.x demands torch>=2.6 and disables itself on 2.4; requests was an implicit dependency of that ComfyUI commit.
RUN python -m pip install "transformers==4.51.3" "tokenizers<0.22" requests \
    && python -c "import transformers, torch, requests; print('transformers', transformers.__version__, 'torch', torch.__version__)"

# latest kornia segfaults on import with torch 2.4 / python 3.11rc1 (comfy_extras/nodes_canny.py imports it)
RUN python -m pip install "kornia==0.7.3" "kornia_rs==0.1.5" \
    && python -c "import kornia; print('kornia', kornia.__version__)"

WORKDIR /app
EXPOSE 8188
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--lowvram", "--disable-auto-launch"]
