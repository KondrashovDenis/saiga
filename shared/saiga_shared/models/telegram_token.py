from datetime import datetime, timedelta
import secrets

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


class TelegramLinkToken(Base):
    """Одноразовый токен для deep-link авторизации/привязки через Telegram.

    Жизненный цикл:
      1. Web создаёт запись (kind='link' или 'login', expires_at = now+10min).
      2. Юзер открывает t.me/<bot>?start=<kind>_<token>.
      3. Бот видит /start, читает запись, привязывает/логинит.
      4. Бот ставит used_at=NOW() — токен больше не валиден.

    Для kind='link' user_id заранее известен (юзер уже авторизован в web).
    Для kind='login' user_id заполняется ботом после того как юзер
    подтвердил вход — web потом поллит и видит появившийся user_id, после
    чего выдаёт session-cookie.
    """

    __tablename__ = "telegram_link_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    kind = Column(String(10), nullable=False)  # 'link' | 'login'

    # Для 'link' — известен сразу. Для 'login' — заполняется ботом.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User")

    @staticmethod
    def generate(kind: str, user_id: int | None, ttl_minutes: int = 10) -> "TelegramLinkToken":
        if kind not in ("link", "login"):
            raise ValueError(f"Unknown kind: {kind}")
        return TelegramLinkToken(
            token=secrets.token_urlsafe(24),
            kind=kind,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_used

    def __repr__(self) -> str:
        return f"<TelegramLinkToken {self.kind}:{self.token[:8]}... user={self.user_id}>"
