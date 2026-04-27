import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select

from config import Config

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

DATABASE_URL = Config.DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///')
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    
    from . import user, conversation, message, setting
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ База данных инициализирована")

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
