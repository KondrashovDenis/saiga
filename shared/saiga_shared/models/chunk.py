"""Chunk — кусок документа с embedding-вектором для cosine search.

Размерность 1024 — соответствует intfloat/multilingual-e5-large из embedding
сервиса. Если потом сменим модель — нужна миграция (drop column + add с новой
размерностью + re-embed всех существующих документов).

HNSW индекс по `embedding vector_cosine_ops` создаётся в Alembic 0004. Это
сильно ускоряет retrieval (O(log n) вместо full scan), но при индексации новых
chunks замедляет insert. Для нашего случая (тысячи документов, не миллионы) — OK.
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


# Размерность вектора. Менять синхронно с EMBEDDING_DIM в embedding/app.py
# и с миграцией Alembic.
CHUNK_EMBEDDING_DIM = 1024


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Порядковый номер chunk'а в документе (0-based). Уникален в рамках документа.
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    # Оценка количества токенов в chunk'е (для дебага и подсчёта прайсинга).
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(CHUNK_EMBEDDING_DIM), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
    )

    def to_dict(self, include_embedding: bool = False) -> dict:
        d = {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_embedding and self.embedding is not None:
            d["embedding"] = list(self.embedding)
        return d

    def __repr__(self) -> str:
        return f"<Chunk doc={self.document_id} idx={self.chunk_index}>"
