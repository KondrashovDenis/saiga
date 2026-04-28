import json

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True
    )

    # ─────── Интерфейс (web) ───────
    ui_theme = Column(String(20), default="auto")  # light | dark | auto
    avatar_style = Column(String(20), default="initials")  # initials | gravatar | custom
    message_animations = Column(Boolean, default=True)
    auto_scroll = Column(Boolean, default=True)
    show_timestamps = Column(Boolean, default=True)
    show_quick_replies = Column(Boolean, default=True)
    enable_reactions = Column(Boolean, default=True)
    markdown_support = Column(Boolean, default=True)

    # ─────── Бот ───────
    notifications_enabled = Column(Boolean, default=True)
    quick_replies_enabled = Column(Boolean, default=True)

    # ─────── LLM настройки ───────
    temperature = Column(Float, default=0.7)
    top_p = Column(Float, default=0.9)
    max_tokens = Column(Integer, default=2048)
    language = Column(String(10), default="ru")

    # ─────── Произвольные дополнительные настройки модели ───────
    model_preferences_json = Column(Text, default="{}")

    user = relationship("User", back_populates="settings")

    @property
    def model_preferences(self) -> dict:
        try:
            return json.loads(self.model_preferences_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @model_preferences.setter
    def model_preferences(self, preferences: dict) -> None:
        self.model_preferences_json = json.dumps(preferences or {})

    def to_dict(self) -> dict:
        return {
            "ui_theme": self.ui_theme,
            "avatar_style": self.avatar_style,
            "message_animations": self.message_animations,
            "auto_scroll": self.auto_scroll,
            "show_timestamps": self.show_timestamps,
            "show_quick_replies": self.show_quick_replies,
            "enable_reactions": self.enable_reactions,
            "markdown_support": self.markdown_support,
            "notifications_enabled": self.notifications_enabled,
            "quick_replies_enabled": self.quick_replies_enabled,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "language": self.language,
            "model_preferences": self.model_preferences,
        }

    def __repr__(self) -> str:
        return f"<Setting user_id={self.user_id}>"
