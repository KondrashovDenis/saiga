"""Документ внутри Knowledge Base — оригинал текста + статус обработки.

Полный извлечённый текст храним (Text, без size limit на уровне БД, ограничение
2 MB применяется на уровне DocumentProcessor). Это позволит позже re-chunk'нуть
с другими параметрами без повторной загрузки PDF.

Статус обработки:
- pending      — создан, ещё не обработан (chunking + embedding не запущены)
- processing   — в работе
- ready        — все chunks с embeddings готовы для retrieval
- failed       — ошибка; см. error_message
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_PROCESSING = "processing"
DOCUMENT_STATUS_READY = "ready"
DOCUMENT_STATUS_FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    kb_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=False)
    # Имя загруженного файла, если из upload. None — для текстов созданных вручную.
    source_filename = Column(String(255), nullable=True)
    # 'pdf' | 'docx' | 'txt' | 'md' | 'manual'
    file_type = Column(String(20), nullable=False, default="manual")
    # Полный извлечённый текст. Лимит 2 MB форсится в DocumentProcessor.
    content = Column(Text, nullable=False)

    status = Column(String(20), nullable=False, default=DOCUMENT_STATUS_PENDING)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "title": self.title,
            "source_filename": self.source_filename,
            "file_type": self.file_type,
            "status": self.status,
            "error_message": self.error_message,
            "chunk_count": len(self.chunks) if self.chunks is not None else 0,
            "content_length": len(self.content) if self.content else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Document {self.id} {self.title!r}>"
