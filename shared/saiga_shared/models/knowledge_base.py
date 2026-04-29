"""RAG knowledge base — контейнер документов для конкретного юзера.

Каждый юзер может иметь несколько KB (например, "звукотерапия", "клиенты"),
в каждой — несколько документов; каждый документ режется на chunks с
embedding-векторами для cosine-search.

В будущем для sochispirit-app те же модели работают в отдельной схеме
БД (cross-schema чтобы не мешаться с saiga-юзерами) — пока всё в public.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Имя для UI
    name = Column(String(120), nullable=False)
    # Слаг для URL (a-z 0-9 -). Уникален в рамках одного владельца.
    slug = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    documents = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_kb_owner_slug"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "document_count": len(self.documents) if self.documents is not None else 0,
        }

    def __repr__(self) -> str:
        return f"<KnowledgeBase {self.owner_id}/{self.slug}>"
