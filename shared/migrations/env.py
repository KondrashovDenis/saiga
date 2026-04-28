"""Alembic env — sync engine, читает DSN из DATABASE_URL.

Запускается из контейнера web (саму миграцию накатываем через
`alembic upgrade head` в entrypoint web). Bot работает с той же БД,
но миграции не запускает — это отдельная ответственность.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from saiga_shared.models import Base

config = context.config

# DSN из окружения. Если в DATABASE_URL прописан async-driver
# (postgresql+asyncpg://) — здесь срезаем его до sync (postgresql://),
# потому что Alembic умеет только sync.
def _to_sync_url(url: str) -> str:
    if not url:
        raise RuntimeError("DATABASE_URL не задан для alembic")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


config.set_main_option("sqlalchemy.url", _to_sync_url(os.environ.get("DATABASE_URL", "")))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
