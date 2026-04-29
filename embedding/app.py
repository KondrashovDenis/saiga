"""Embedding service для saiga RAG-инфраструктуры.

Эндпоинты:
- GET  /healthz                — pure healthcheck, без обращения к модели.
- POST /embed       {text}     — embed одной строки, returns {vector: [..]}.
- POST /embed/batch {texts:[]} — batch embedding, returns {vectors: [[..],..]}.

Модель `intfloat/multilingual-e5-large` (1024 dim) — multilingual, поддерживает
русский на уровне с английским. Для e5-моделей принято префиксить:
- индексируемые тексты: "passage: <text>"
- запросы:              "query: <text>"
Префикс выставляется через query_string `kind=passage` или `kind=query`
(default = passage, потому что embed чаще нужен для индексации документов).

Auth: Bearer-токен из EMBEDDING_API_KEY env. Если ключ не задан — сервис
запускается, но падает в startup-error: на homeserver expose делаем только
во внутреннюю сеть, но без token приватность по сети — не argument.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
EMBEDDING_DIM = 1024  # для multilingual-e5-large; для small=384, base=768
API_KEY = os.environ.get("EMBEDDING_API_KEY", "").strip()

# CPU-bound encode гоняем в отдельном пуле, чтобы async event loop не блокировался.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed-")


_model: SentenceTransformer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    if not API_KEY:
        # Не запускаемся без токена — иначе любой кто прорвался во внутреннюю
        # сеть (web, bot, sochispirit-app в будущем) сможет ddos'ить модель.
        raise RuntimeError("EMBEDDING_API_KEY не задан в окружении")
    _model = SentenceTransformer(MODEL_NAME, device="cpu")
    # warmup: encode("") прогревает кеш токенизатора и проверяет что веса легли.
    _model.encode("warmup", convert_to_numpy=True, normalize_embeddings=True)
    yield
    _executor.shutdown(wait=False)


app = FastAPI(title="saiga-embedding", lifespan=lifespan)


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8192)
    kind: Literal["passage", "query"] = "passage"


class EmbedResponse(BaseModel):
    vector: list[float]
    model: str
    dim: int


class BatchEmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=64)
    kind: Literal["passage", "query"] = "passage"


class BatchEmbedResponse(BaseModel):
    vectors: list[list[float]]
    model: str
    dim: int


def _check_auth(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required")
    if auth.removeprefix("Bearer ").strip() != API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def _prefix(text: str, kind: str) -> str:
    return f"{kind}: {text}"


def _encode_sync(texts: list[str]) -> list[list[float]]:
    # normalize_embeddings=True — критично: pgvector cosine-distance работает
    # быстрее и стабильнее на нормализованных векторах (cosine == 1 - dot).
    arr = _model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return arr.tolist()


@app.get("/healthz")
async def healthz():
    # Не требуем auth — Caddy/compose могут пинговать.
    return {"status": "ok", "model": MODEL_NAME, "dim": EMBEDDING_DIM, "loaded": _model is not None}


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest, request: Request):
    _check_auth(request)
    texts = [_prefix(req.text, req.kind)]
    loop = asyncio.get_running_loop()
    vectors = await loop.run_in_executor(_executor, _encode_sync, texts)
    return EmbedResponse(vector=vectors[0], model=MODEL_NAME, dim=EMBEDDING_DIM)


@app.post("/embed/batch", response_model=BatchEmbedResponse)
async def embed_batch(req: BatchEmbedRequest, request: Request):
    _check_auth(request)
    texts = [_prefix(t, req.kind) for t in req.texts]
    loop = asyncio.get_running_loop()
    vectors = await loop.run_in_executor(_executor, _encode_sync, texts)
    return BatchEmbedResponse(vectors=vectors, model=MODEL_NAME, dim=EMBEDDING_DIM)
