import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select

from config import Config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _to_async_url(url: str) -> str:
    """Конвертирует sync DSN в async-вариант для SQLAlchemy.

    sqlite:///path             → sqlite+aiosqlite:///path
    postgresql://user@host/db  → postgresql+asyncpg://user@host/db
    Если уже с async-driver — возвращаем как есть.
    """
    if url.startswith('sqlite+aiosqlite:') or url.startswith('postgresql+asyncpg:'):
        return url
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    if url.startswith('postgres://'):  # legacy
        return url.replace('postgres://', 'postgresql+asyncpg://', 1)
    raise ValueError(f"Unsupported DATABASE_URL scheme: {url[:30]}...")


DATABASE_URL = _to_async_url(Config.DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    os.makedirs(Config.DATA_DIR, exist_ok=True)

    from . import user, conversation, message, setting

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ База данных инициализирована (%s)", DATABASE_URL.split('@')[-1])


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_or_create_user(telegram_id: int, **kwargs):
    async with async_session() as session:
        from .user import User
        from .setting import Setting

        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=telegram_id, **kwargs)
            session.add(user)
            await session.commit()

            settings = Setting(user_id=user.id)
            session.add(settings)
            await session.commit()

        return user
