"""Async SQLAlchemy engine для бота поверх shared-моделей.

Схему накатывает Alembic из web-контейнера. `init_db()` оставлен как no-op
для совместимости (если main.py вызывает его при старте).
"""
import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import select

from config import Config
from saiga_shared.models import Base, User, Setting  # noqa: F401 — re-exports

logger = logging.getLogger(__name__)


def _to_async_url(url: str) -> str:
    """Конвертирует sync DSN в async-вариант для SQLAlchemy.

    sqlite:///path             → sqlite+aiosqlite:///path
    postgresql://user@host/db  → postgresql+asyncpg://user@host/db
    Если уже с async-driver — возвращаем как есть.
    """
    if url.startswith("sqlite+aiosqlite:") or url.startswith("postgresql+asyncpg:"):
        return url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise ValueError(f"Unsupported DATABASE_URL scheme: {url[:30]}...")


DATABASE_URL = _to_async_url(Config.DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Раньше делал create_all — теперь нет.

    Схема накатывается Alembic из web-контейнера. Здесь оставлена пустая
    функция для совместимости со старым main.py, который её вызывает.
    """
    logger.info("DB ready (%s) — schema managed by Alembic", DATABASE_URL.split("@")[-1])


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_or_create_user(telegram_id: int, **kwargs):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # auth_method для тех, кто пришёл через бота — 'telegram'
            kwargs.setdefault("auth_method", "telegram")
            user = User(telegram_id=telegram_id, **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            settings = Setting(user_id=user.id)
            session.add(settings)
            await session.commit()

        return user
