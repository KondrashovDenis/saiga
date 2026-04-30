"""FastAPI сервис image-gen для Glow.

5.2a: SD 1.5 base, txt2img.
5.2b: + ControlNet (canny) для гибридного pipeline:
      Python рисует геометрию -> control image -> SD добавляет стиль/свечение/цвет.
5.2c: + опциональный LoRA (если найдём sacred geometry для SD 1.5).

Lazy load: SD 1.5 при старте, ControlNet — при первом /generate-controlnet,
чтобы не держать ~1.5 GB в VRAM если Кристалл не используется.

P104-100 (Pascal sm_61, 8 GB VRAM):
    - SD 1.5 fp16 + ControlNet ~3-4 GB на pipeline + ~2 GB на активации = ~6 GB.
    - 30 steps × 512×512: txt2img ~18 сек, controlnet ~25-30 сек.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Optional

import torch
from PIL import Image
from diffusers import (
    ControlNetModel,
    DPMSolverMultistepScheduler,
    StableDiffusionControlNetPipeline,
    StableDiffusionPipeline,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('imagegen')

SD_MODEL_ID = os.environ.get('SD_MODEL_ID', 'runwayml/stable-diffusion-v1-5')
CONTROLNET_MODEL_ID = os.environ.get('CONTROLNET_MODEL_ID', 'lllyasviel/sd-controlnet-canny')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DTYPE = torch.float16 if DEVICE == 'cuda' else torch.float32

app = FastAPI(title='Saiga ImageGen', version='5.2b')

# Глобальные pipeline'ы — txt2img при старте, controlnet lazy
sd_pipeline: Optional[StableDiffusionPipeline] = None
cn_pipeline: Optional[StableDiffusionControlNetPipeline] = None


def _make_scheduler(pipe):
    return DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)


@app.on_event('startup')
async def load_pipeline():
    global sd_pipeline
    log.info(f'Loading SD pipeline: {SD_MODEL_ID} on {DEVICE} ({DTYPE})')
    log.info(f'CUDA: {torch.cuda.is_available()} '
             f'devices: {torch.cuda.device_count()} '
             f'name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else "n/a"}')

    pipe = StableDiffusionPipeline.from_pretrained(
        SD_MODEL_ID,
        torch_dtype=DTYPE,
        safety_checker=None,
        requires_safety_checker=False,
    )
    pipe.scheduler = _make_scheduler(pipe)
    pipe.enable_attention_slicing()
    pipe = pipe.to(DEVICE)
    sd_pipeline = pipe
    log.info('SD pipeline ready.')


def _ensure_controlnet():
    """Lazy-load ControlNet pipeline при первом вызове."""
    global cn_pipeline
    if cn_pipeline is not None:
        return cn_pipeline

    log.info(f'Loading ControlNet: {CONTROLNET_MODEL_ID}')
    cn = ControlNetModel.from_pretrained(CONTROLNET_MODEL_ID, torch_dtype=DTYPE)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        SD_MODEL_ID,
        controlnet=cn,
        torch_dtype=DTYPE,
        safety_checker=None,
        requires_safety_checker=False,
    )
    pipe.scheduler = _make_scheduler(pipe)
    pipe.enable_attention_slicing()
    pipe = pipe.to(DEVICE)
    cn_pipeline = pipe
    log.info('ControlNet pipeline ready.')
    return cn_pipeline


# ─── Models ─────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    negative_prompt: Optional[str] = Field(default='', max_length=1000)
    steps: int = Field(default=30, ge=10, le=80)
    cfg: float = Field(default=7.5, ge=1.0, le=15.0)
    width: int = Field(default=512, ge=256, le=768)
    height: int = Field(default=512, ge=256, le=768)
    seed: Optional[int] = Field(default=None)


class ControlNetRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    negative_prompt: Optional[str] = Field(default='', max_length=1000)
    # base64-encoded PNG/JPG. Должен быть тех же размеров что output (или
    # будет автоматически отресайзен через PIL).
    control_image_b64: str = Field(..., min_length=100)
    controlnet_conditioning_scale: float = Field(default=1.0, ge=0.0, le=2.0,
        description='Сила влияния control image. 1.0 — стандарт, 0.5 — мягко, 1.5 — жёстко')
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


# ─── Endpoints ───────────────────────────────────────────────────────

@app.get('/healthz')
async def healthz():
    cuda_ok = torch.cuda.is_available()
    info = {
        'status': 'ok' if sd_pipeline is not None else 'loading',
        'device': DEVICE,
        'dtype': str(DTYPE),
        'cuda_available': cuda_ok,
        'cuda_devices': torch.cuda.device_count() if cuda_ok else 0,
        'sd_pipeline_loaded': sd_pipeline is not None,
        'controlnet_pipeline_loaded': cn_pipeline is not None,
    }
    if cuda_ok:
        info['gpu_name'] = torch.cuda.get_device_name(0)
        info['vram_used_gb'] = round(torch.cuda.memory_allocated() / 1024 ** 3, 2)
        info['vram_total_gb'] = round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 2)
    return info


@app.post('/generate', response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if sd_pipeline is None:
        raise HTTPException(status_code=503, detail='SD pipeline not loaded yet')

    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2**31
    generator = torch.Generator(device=DEVICE).manual_seed(seed)

    log.info(f'[gen] prompt={req.prompt[:80]!r} steps={req.steps} cfg={req.cfg} '
             f'{req.width}x{req.height} seed={seed}')
    t0 = time.time()
    try:
        out = sd_pipeline(
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
    return GenerateResponse(
        image_b64=base64.b64encode(buf.getvalue()).decode('ascii'),
        width=req.width,
        height=req.height,
        elapsed_sec=round(elapsed, 2),
        seed=seed,
    )


@app.post('/generate-controlnet', response_model=GenerateResponse)
async def generate_controlnet(req: ControlNetRequest):
    """Гибридная генерация: control image задаёт композицию, SD добавляет стиль.

    Для Кристалла Души: Python нарисует Платоново тело + сакральную геометрию,
    SD сделает её эфирной/светящейся/цветной по prompt.
    """
    pipe = _ensure_controlnet()

    # Декодируем control image
    try:
        img_bytes = base64.b64decode(req.control_image_b64)
        control_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        if control_img.size != (req.width, req.height):
            log.info(f'[cn] resizing control {control_img.size} -> {req.width}x{req.height}')
            control_img = control_img.resize((req.width, req.height), Image.LANCZOS)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Invalid control_image_b64: {e}')

    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2**31
    generator = torch.Generator(device=DEVICE).manual_seed(seed)

    log.info(f'[cn] prompt={req.prompt[:80]!r} steps={req.steps} cfg={req.cfg} '
             f'cn_scale={req.controlnet_conditioning_scale} '
             f'{req.width}x{req.height} seed={seed}')
    t0 = time.time()
    try:
        out = pipe(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt or '',
            image=control_img,
            num_inference_steps=req.steps,
            guidance_scale=req.cfg,
            controlnet_conditioning_scale=req.controlnet_conditioning_scale,
            width=req.width,
            height=req.height,
            generator=generator,
        )
        image = out.images[0]
    except Exception as e:
        log.exception(f'[cn] failed: {e}')
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.time() - t0
    log.info(f'[cn] done in {elapsed:.1f}s')
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return GenerateResponse(
        image_b64=base64.b64encode(buf.getvalue()).decode('ascii'),
        width=req.width,
        height=req.height,
        elapsed_sec=round(elapsed, 2),
        seed=seed,
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
