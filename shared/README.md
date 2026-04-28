# saiga_shared

Общие SQLAlchemy 2.0 модели для web и bot. Plain-SA `DeclarativeBase` без привязки к Flask или async.

## Использование

В web (sync):
```python
from saiga_shared.models import Base, User, Conversation, Message, Setting
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy(model_class=Base)  # web получает все модели через db.Model
```

В bot (async):
```python
from saiga_shared.models import Base, User, Conversation, Message, Setting
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://...")
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

## Миграции (Alembic)

Запуск с web-хоста (где есть DATABASE_URL):

```bash
# Применить все миграции
cd /app/shared
DATABASE_URL=postgresql://... alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "add column foo"
```

`env.py` понимает и async DSN — обрезает до sync (alembic умеет только sync).
