"""Knowledge Base API — JSON only (UI следующей сессией).

Все эндпоинты под /api/kb/* требуют login. Юзер может работать ТОЛЬКО со
своими KB (owner_id фильтр на уровне queries и в retrieval helper).

Endpoints:
- POST   /api/kb/                          {name, slug, description?}     — создать KB
- GET    /api/kb/                                                          — список своих KB
- GET    /api/kb/<id>                                                      — детали KB + список documents
- DELETE /api/kb/<id>                                                      — удалить KB (cascade documents+chunks)
- POST   /api/kb/<id>/documents            file=...  ИЛИ {title, content} — загрузить документ + chunk + embed
- DELETE /api/kb/<id>/documents/<doc_id>                                   — удалить документ
- POST   /api/kb/<id>/search               {q, top_k?, max_distance?}     — cosine search

Embedding service вызывается синхронно в обработчике upload — для документов
до пары MB это секунды, для больших — десятки секунд. Если станет узким
местом — выносим в celery/RQ task. Пока проще и без новых зависимостей.
"""
from __future__ import annotations

import os
import re
import tempfile

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import select
from werkzeug.utils import secure_filename

from database import db
from extensions import limiter
from models.knowledge_base import (
    KnowledgeBase,
    Document,
    Chunk,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_READY,
    DOCUMENT_STATUS_FAILED,
)
from utils.document_processor import DocumentProcessor
from utils.file_validator import FileValidator
from saiga_shared.rag.chunker import chunk_text, ChunkerConfig
from saiga_shared.rag.embedding_client import EmbeddingClient
from saiga_shared.rag.retrieval import search_chunks


kb_bp = Blueprint("kb", __name__, url_prefix="/api/kb")


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}[a-z0-9]$")


def _embedding_client() -> EmbeddingClient:
    """Подтягиваем EmbeddingClient из env. Падаем явно если конфиг кривой."""
    base_url = os.environ.get("EMBEDDING_API_URL", "http://saiga-embedding:8000")
    api_key = os.environ.get("EMBEDDING_API_KEY", "").strip()
    if not api_key:
        abort(500, description="EMBEDDING_API_KEY не задан в web/.env")
    return EmbeddingClient(base_url=base_url, api_key=api_key, timeout=120.0)


def _ensure_owner(kb: KnowledgeBase) -> None:
    if kb.owner_id != current_user.id:
        abort(404)  # 404 а не 403 — не палим существование чужой KB


def _slugify_or_validate(value: str) -> str:
    value = value.strip().lower()
    # Простой slugify: пробелы → дефис, прочее не-[a-z0-9-] выкидываем.
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not _SLUG_RE.match(value):
        abort(400, description="slug должен быть [a-z0-9-]{2..120}, начинаться/заканчиваться буквой/цифрой")
    return value


# ─────────────── KB CRUD ───────────────

@kb_bp.route("/", methods=["GET"])
@login_required
def list_kbs():
    rows = db.session.execute(
        select(KnowledgeBase).where(KnowledgeBase.owner_id == current_user.id)
        .order_by(KnowledgeBase.updated_at.desc())
    ).scalars().all()
    return jsonify({"items": [kb.to_dict() for kb in rows]})


@kb_bp.route("/", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def create_kb():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    slug = payload.get("slug") or name
    description = (payload.get("description") or "").strip() or None

    if not name or len(name) > 120:
        abort(400, description="name обязателен (1..120 символов)")
    slug = _slugify_or_validate(slug)

    kb = KnowledgeBase(
        owner_id=current_user.id,
        name=name,
        slug=slug,
        description=description,
    )
    db.session.add(kb)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        abort(409, description="KB с таким slug уже существует у вас")
    return jsonify(kb.to_dict()), 201


@kb_bp.route("/<int:kb_id>", methods=["GET"])
@login_required
def get_kb(kb_id):
    kb = db.session.get(KnowledgeBase, kb_id)
    if not kb:
        abort(404)
    _ensure_owner(kb)
    docs = db.session.execute(
        select(Document).where(Document.kb_id == kb.id).order_by(Document.created_at.desc())
    ).scalars().all()
    return jsonify({
        **kb.to_dict(),
        "documents": [d.to_dict() for d in docs],
    })


@kb_bp.route("/<int:kb_id>", methods=["DELETE"])
@login_required
def delete_kb(kb_id):
    kb = db.session.get(KnowledgeBase, kb_id)
    if not kb:
        abort(404)
    _ensure_owner(kb)
    db.session.delete(kb)
    db.session.commit()
    return jsonify({"deleted": True})


# ─────────────── Documents ───────────────

@kb_bp.route("/<int:kb_id>/documents", methods=["POST"])
@login_required
@limiter.limit("20 per hour; 100 per day")
def upload_document(kb_id):
    """Принимает либо multipart-file, либо JSON {title, content}.

    multipart: form key "file" — pdf/docx/txt/md, обрабатывается через
        DocumentProcessor (sandbox subprocess для PDF/DOCX).
    JSON: используется для текстовых документов вставленных вручную.

    После сохранения document — синхронно делаем chunking + embedding.
    Если embedding service недоступен — document остаётся в status='failed'
    с сообщением в error_message, но запись не теряется (можно ре-индексить позже).
    """
    kb = db.session.get(KnowledgeBase, kb_id)
    if not kb:
        abort(404)
    _ensure_owner(kb)

    # ───── Source: JSON или multipart ─────
    if request.content_type and request.content_type.startswith("application/json"):
        payload = request.get_json(silent=True) or {}
        title = (payload.get("title") or "").strip()
        content = (payload.get("content") or "").strip()
        if not title or not content:
            abort(400, description="title и content обязательны для JSON-варианта")
        if len(content) > 2 * 1024 * 1024:
            abort(400, description="content > 2MB — слишком большой документ")
        file_type = "manual"
        source_filename = None
    else:
        if "file" not in request.files:
            abort(400, description="Файл не найден в запросе")
        file = request.files["file"]
        is_valid, msg = FileValidator.validate_file(file)
        if not is_valid:
            abort(400, description=msg)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(file.filename)[1]
            ) as tmp:
                temp_path = tmp.name
                file.seek(0)
                tmp.write(file.read())
            content, file_type = DocumentProcessor.process_document(temp_path)
            source_filename = secure_filename(file.filename) or file.filename
            title = (request.form.get("title") or source_filename or "Без названия").strip()
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    # ───── Persist Document ─────
    doc = Document(
        kb_id=kb.id,
        title=title[:255],
        source_filename=source_filename[:255] if source_filename else None,
        file_type=file_type,
        content=content,
        status=DOCUMENT_STATUS_PROCESSING,
    )
    db.session.add(doc)
    db.session.commit()

    # ───── Chunk + embed (sync) ─────
    try:
        chunks = chunk_text(content, ChunkerConfig())
        if not chunks:
            doc.status = DOCUMENT_STATUS_FAILED
            doc.error_message = "После chunking осталось 0 кусков (документ пуст?)"
            db.session.commit()
            return jsonify({"document": doc.to_dict()}), 400

        client = _embedding_client()
        # Batch embed по 32 (e5-large на CPU за 32 текста ~3-5s).
        BATCH = 32
        for batch_start in range(0, len(chunks), BATCH):
            batch = chunks[batch_start:batch_start + BATCH]
            vectors = client.embed_batch([c["text"] for c in batch], kind="passage")
            for c, vec in zip(batch, vectors):
                db.session.add(Chunk(
                    document_id=doc.id,
                    chunk_index=c["index"],
                    text=c["text"],
                    token_count=c.get("token_count"),
                    embedding=vec,
                ))
            db.session.commit()

        doc.status = DOCUMENT_STATUS_READY
        doc.error_message = None
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        doc = db.session.get(Document, doc.id)
        if doc is not None:
            doc.status = DOCUMENT_STATUS_FAILED
            doc.error_message = f"{type(e).__name__}: {e}"[:1000]
            db.session.commit()
        return jsonify({
            "error": "embedding_failed",
            "message": str(e),
            "document": doc.to_dict() if doc else None,
        }), 502

    return jsonify({"document": doc.to_dict()}), 201


@kb_bp.route("/<int:kb_id>/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(kb_id, doc_id):
    kb = db.session.get(KnowledgeBase, kb_id)
    if not kb:
        abort(404)
    _ensure_owner(kb)
    doc = db.session.get(Document, doc_id)
    if not doc or doc.kb_id != kb.id:
        abort(404)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"deleted": True})


# ─────────────── Search ───────────────

@kb_bp.route("/<int:kb_id>/search", methods=["POST"])
@login_required
@limiter.limit("60 per hour")
def search(kb_id):
    kb = db.session.get(KnowledgeBase, kb_id)
    if not kb:
        abort(404)
    _ensure_owner(kb)

    payload = request.get_json(silent=True) or {}
    q = (payload.get("q") or "").strip()
    if not q:
        abort(400, description="q обязателен")
    top_k = int(payload.get("top_k") or 5)
    top_k = max(1, min(top_k, 20))
    max_distance = payload.get("max_distance")
    if max_distance is not None:
        max_distance = float(max_distance)

    client = _embedding_client()
    query_vec = client.embed(q, kind="query")

    hits = search_chunks(
        db.session,
        query_vec,
        kb_ids=[kb.id],
        owner_id=current_user.id,
        top_k=top_k,
        max_distance=max_distance,
    )
    return jsonify({
        "query": q,
        "kb_id": kb.id,
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "document_title": h.document_title,
                "chunk_index": h.chunk_index,
                "text": h.text,
                "distance": h.distance,
            }
            for h in hits
        ],
    })
