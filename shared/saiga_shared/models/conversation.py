import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="Новый диалог")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model_used = Column(String(100), nullable=True)
    is_shared = Column(Boolean, default=False)
    share_token = Column(String(64), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
    )

    def generate_share_token(self) -> str:
        self.share_token = str(uuid.uuid4())
        self.is_shared = True
        return self.share_token

    def disable_sharing(self) -> None:
        self.share_token = None
        self.is_shared = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "model_used": self.model_used,
            "is_shared": self.is_shared,
            "message_count": len(self.messages) if self.messages else 0,
        }

    def __repr__(self) -> str:
        return f"<Conversation {self.title}>"
