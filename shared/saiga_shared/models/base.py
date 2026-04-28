from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Единый DeclarativeBase для всех моделей saiga.

    Используется и в web (sync engine через Flask-SQLAlchemy с model_class=Base),
    и в bot (async engine через asyncpg). Сами модели не привязаны к sync/async —
    разница только на уровне engine.
    """
    pass
