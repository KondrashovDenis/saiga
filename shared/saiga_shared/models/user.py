from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from saiga_shared.models.base import Base


class User(Base):
    """Пользователь — вход через email/password И/ИЛИ Telegram.

    Используется и в web (через Flask-Login), и в bot. UserMixin интерфейс
    встроен напрямую (4 свойства: is_authenticated, is_active, is_anonymous,
    get_id) — чтобы shared не зависел от Flask.

    werkzeug.security импортируется лениво — бот не использует password-методы,
    а werkzeug в bot/requirements.txt не входит.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # email/password (опционально — может быть только Telegram)
    username = Column(String(64), unique=True, nullable=True, index=True)
    email = Column(String(120), unique=True, nullable=True, index=True)
    password_hash = Column(String(256), nullable=True)

    # Telegram (опционально — может быть только email)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    telegram_username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)
    language_code = Column(String(10), default="ru")

    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    is_active_user = Column("is_active", Boolean, default=True)
    # Подтверждён ли email через ссылку. Для telegram-only юзеров не используется
    # (TG-аккаунт верифицирован самим Telegram). См. needs_email_verification.
    email_verified = Column(Boolean, default=False, nullable=False)

    # 'email', 'telegram', 'both'
    auth_method = Column(String(20), default="email")

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    settings = relationship(
        "Setting",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ───────────── Flask-Login UserMixin интерфейс ─────────────
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return bool(self.is_active_user)

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)

    # ───────────── Password helpers (web only — werkzeug lazy) ─────────────
    # scrypt — memory-hard hash, устойчивый к GPU/ASIC-атакам. В stdlib (Python
    # hashlib.scrypt), без extra deps. Werkzeug 3.x делает scrypt дефолтом и
    # убирает argon2 (broken в 2.3.7, deprecated в 3.0). Старые PBKDF2-хеши
    # читаются через check_password_hash (werkzeug парсит prefix), при первом
    # успешном логине web rehash-ит их в scrypt —
    # см. routes/auth.py login + needs_password_rehash.
    PASSWORD_HASH_METHOD = "scrypt"

    def set_password(self, password: str) -> None:
        if not password:
            return
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password, method=self.PASSWORD_HASH_METHOD)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @property
    def needs_password_rehash(self) -> bool:
        """True если хеш не scrypt — нужно перехешировать после успешного логина."""
        return bool(self.password_hash) and not self.password_hash.startswith("scrypt")

    @property
    def needs_email_verification(self) -> bool:
        """True если юзер логинится паролем и email ещё не подтверждён.

        Для telegram-only юзеров (auth_method='telegram', нет password_hash)
        возвращает False — TG сам по себе верификация.
        """
        return bool(self.password_hash) and not self.email_verified

    # ───────────── Telegram linking ─────────────
    def link_telegram(self, telegram_id, telegram_username=None,
                      first_name=None, last_name=None) -> None:
        self.telegram_id = telegram_id
        self.telegram_username = telegram_username
        self.first_name = first_name
        self.last_name = last_name
        if self.auth_method == "email":
            self.auth_method = "both"

    def unlink_telegram(self) -> bool:
        self.telegram_id = None
        self.telegram_username = None
        if self.auth_method == "both":
            self.auth_method = "email"
            return True
        if self.auth_method == "telegram":
            return False  # нельзя отвязать единственный способ входа
        return True

    @property
    def display_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.username:
            return self.username
        if self.telegram_username:
            return f"@{self.telegram_username}"
        return f"User {self.id}"

    @property
    def can_login_with_password(self) -> bool:
        return self.password_hash is not None

    @property
    def can_login_with_telegram(self) -> bool:
        return self.telegram_id is not None

    def __repr__(self) -> str:
        return f"<User {self.display_name}>"
