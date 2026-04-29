"""Retrieval helper — cosine search по chunks.embedding.

Работает поверх sync SA Session (Flask-SQLAlchemy в web). Для async из bot —
обернёшь в `await session.run_sync(lambda s: search_chunks(s, ...))`.

Cosine distance в pgvector выражается оператором `<=>`. У SA-колонки
`Vector` есть метод `.cosine_distance(...)` — он рендерит этот оператор и
позволяет SA планировать использование HNSW индекса.

Ограничение: фильтрация (kb_id) применяется ДО ORDER BY, поэтому HNSW индекс
может не использоваться полностью для очень узких kb_id-фильтров — Postgres
выберет seq scan + sort. Для тысяч chunks это всё равно быстро (<10ms).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from saiga_shared.models.chunk import Chunk
from saiga_shared.models.document import Document
from saiga_shared.models.knowledge_base import KnowledgeBase


@dataclass
class RetrievalHit:
    chunk_id: int
    document_id: int
    document_title: str
    kb_id: int
    chunk_index: int
    text: str
    distance: float  # cosine distance, 0 = идентичны, 2 = противоположны


def search_chunks(
    session: Session,
    query_embedding: Sequence[float],
    *,
    kb_ids: Sequence[int] | None = None,
    owner_id: int | None = None,
    top_k: int = 5,
    max_distance: float | None = None,
) -> list[RetrievalHit]:
    """Найти top-K chunks ближайших к query_embedding по cosine.

    Args:
        session: SA Session (sync).
        query_embedding: 1024-мерный вектор (e5 query-prefix должен быть
            применён ДО embedding'а — это работа embedding_client.embed(kind=query)).
        kb_ids: если задан — ищем только в этих KB.
        owner_id: если задан — ограничиваем KB этого юзера (защита от
            cross-user leak в API). Применяется join'ом на knowledge_bases.
        top_k: сколько hits вернуть.
        max_distance: если задан — отбрасываем hits с distance > max_distance.
            Для нормализованных e5 cosine distance < 0.4 = очень близко,
            < 0.7 = семантически связано, > 1.0 = почти не связано.

    Returns:
        Отсортированный по distance ASC список RetrievalHit.
    """
    # Cosine distance через SA. distance ASC = ближе сверху.
    distance = Chunk.embedding.cosine_distance(list(query_embedding)).label("distance")

    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.text,
            Document.title,
            Document.kb_id,
            distance,
        )
        .join(Document, Document.id == Chunk.document_id)
    )

    if kb_ids:
        stmt = stmt.where(Document.kb_id.in_(list(kb_ids)))

    if owner_id is not None:
        stmt = stmt.join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
        stmt = stmt.where(KnowledgeBase.owner_id == owner_id)

    stmt = stmt.order_by(distance.asc()).limit(top_k)

    rows = session.execute(stmt).all()
    hits = [
        RetrievalHit(
            chunk_id=r[0],
            document_id=r[1],
            chunk_index=r[2],
            text=r[3],
            document_title=r[4],
            kb_id=r[5],
            distance=float(r[6]),
        )
        for r in rows
    ]

    if max_distance is not None:
        hits = [h for h in hits if h.distance <= max_distance]

    return hits
