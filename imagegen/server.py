"""FastAPI сервис image-gen для Glow.

5.2a (текущий минимум):
    - SD 1.5 base, txt2img только.
    - При первом старте скачивает SD 1.5 в /models/hf_cache (около 4 GB).
    - Endpoint POST /generate {prompt, negative_prompt, steps, cfg, width, height}
      возвращает PNG base64.

5.2b добавит ControlNet + endpoint /generate-controlnet
5.2c добавит Sacred Geometry LoRA

P104-100 (Pascal sm_61, 8 GB VRAM):
    - SD 1.5 fp16: pipeline ~2.5 GB. С activation/encoder = ~4-5 GB на инференс.
    - Скорость на 1080-эквиваленте: 50 steps × 512×512 ~ 30-60 секунд.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Optional

import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('imagegen')

SD_MODEL_ID = os.environ.get('SD_MODEL_ID', 'runwayml/stable-diffusion-v1-5')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DTYPE = torch.float16 if DEVICE == 'cuda' else torch.float32

app = FastAPI(title='Saiga ImageGen', version='5.2a')

# Глобальный pipeline — загружается при старте, переиспользуется между запросами
pipeline: Optional[StableDiffusionPipeline] = None


@app.on_event('startup')
async def load_pipeline():
    global pipeline
    log.info(f'Loading SD pipeline: {SD_MODEL_ID} on {DEVICE} ({DTYPE})')
    log.info(f'CUDA available: {torch.cuda.is_available()}, '
             f'devices: {torch.cuda.device_count()}, '
             f'name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else "n/a"}')

    pipe = StableDiffusionPipeline.from_pretrained(
        SD_MODEL_ID,
        torch_dtype=DTYPE,
        safety_checker=None,  # отключаем NSFW filter — Кристалл не порно
        requires_safety_checker=False,
    )
    # DPMSolver быстрее DDIM при том же качестве
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    # Memory-efficient attention для Pascal (xformers нет, но attention slicing помогает)
    pipe.enable_attention_slicing()
    pipe = pipe.to(DEVICE)
    pipeline = pipe
    log.info('Pipeline ready.')


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    negative_prompt: Optional[str] = Field(default='', max_length=1000)
    steps: int = Field(default=30, ge=10, le=80)
    cfg: float = Field(default=7.5, ge=1.0, le=15.0)
    width: int = Field(default=512, ge=256, le=768)
    height: int = Field(default=512, ge=256, le=768)
    seed: Optional[int] = Field(default=None)


class GenerateResponse(BaseModel):
    image_b64: str
    width: int
    height: int
    elapsed_sec: float
    seed: int


@app.get('/healthz')
async def healthz():
    cuda_ok = torch.cuda.is_available()
    info = {
        'status': 'ok' if pipeline is not None else 'loading',
        'device': DEVICE,
        'dtype': str(DTYPE),
        'cuda_available': cuda_ok,
        'cuda_devices': torch.cuda.device_count() if cuda_ok else 0,
        'pipeline_loaded': pipeline is not None,
    }
    if cuda_ok:
        info['gpu_name'] = torch.cuda.get_device_name(0)
        info['vram_used_gb'] = round(torch.cuda.memory_allocated() / 1024 ** 3, 2)
        info['vram_total_gb'] = round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 2)
    return info


@app.post('/generate', response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if pipeline is None:
        raise HTTPException(status_code=503, detail='Pipeline not loaded yet')

    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2**31
    generator = torch.Generator(device=DEVICE).manual_seed(seed)

    log.info(f'[gen] prompt={req.prompt[:80]!r} steps={req.steps} cfg={req.cfg} '
             f'{req.width}x{req.height} seed={seed}')

    t0 = time.time()
    try:
        out = pipeline(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt or '',
            num_inference_steps=req.steps,
            guidance_scale=req.cfg,
            width=req.width,
            height=req.height,
            generator=generator,
        )
        image = out.images[0]
    except Exception as e:
        log.exception(f'[gen] failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - t0
    log.info(f'[gen] done in {elapsed:.1f}s')

    buf = io.BytesIO()
    image.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode('ascii')

    return GenerateResponse(
        image_b64=img_b64,
        width=req.width,
        height=req.height,
        elapsed_sec=round(elapsed, 2),
        seed=seed,
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
