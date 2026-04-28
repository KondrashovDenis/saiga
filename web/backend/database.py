"""Flask-SQLAlchemy инициализация поверх shared-моделей.

`db.Model` указывает на наш Base из saiga_shared, поэтому модели
зарегистрированы в одной metadata и для web (sync), и для bot (async).
Схему накатывает Alembic — `db.create_all()` больше не используется.
"""
from flask_sqlalchemy import SQLAlchemy
from saiga_shared.models import Base

db = SQLAlchemy(model_class=Base)


def init_db(app):
    """Подключает SQLAlchemy к Flask-приложению.

    Миграции — отдельной командой `alembic upgrade head` в entrypoint
    web-контейнера (см. web/backend/entrypoint.sh). Здесь схему не создаём.
    """
    db.init_app(app)
