"""Тесты конвертера DATABASE_URL → async-вариант для SQLAlchemy.

_to_async_url() — критичная функция: ошибочный вывод сломает init БД при старте бота.
"""
import pytest

from models.database import _to_async_url


@pytest.mark.parametrize('inp, expected', [
    # sqlite
    ('sqlite:///app.db',
     'sqlite+aiosqlite:///app.db'),
    ('sqlite:////absolute/path/to.db',
     'sqlite+aiosqlite:////absolute/path/to.db'),

    # postgresql
    ('postgresql://user:pwd@host:5432/saiga',
     'postgresql+asyncpg://user:pwd@host:5432/saiga'),
    ('postgresql://saiga_app:secret@saiga-tunnel:5432/saiga',
     'postgresql+asyncpg://saiga_app:secret@saiga-tunnel:5432/saiga'),

    # postgres:// (legacy alias, до 2017 года)
    ('postgres://u:p@h/db',
     'postgresql+asyncpg://u:p@h/db'),

    # Уже async — не должны трогать
    ('sqlite+aiosqlite:///app.db',
     'sqlite+aiosqlite:///app.db'),
    ('postgresql+asyncpg://u:p@h/db',
     'postgresql+asyncpg://u:p@h/db'),
])
def test_to_async_url_valid(inp, expected):
    assert _to_async_url(inp) == expected


@pytest.mark.parametrize('inp', [
    'mysql://u:p@h/db',
    'mongodb://localhost:27017',
    'redis://localhost:6379',
    'plain string',
    'http://example.com/db',
])
def test_to_async_url_unsupported_raises(inp):
    """Неизвестные схемы должны падать с ValueError на старте — лучше fail fast,
    чем silently коннектиться не туда."""
    with pytest.raises(ValueError, match='Unsupported DATABASE_URL'):
        _to_async_url(inp)


def test_to_async_url_replaces_only_scheme():
    """Не должны менять что-то кроме префикса — пароль/путь не трогаем."""
    inp = 'postgresql://user:p@ss%40word@host/db'
    out = _to_async_url(inp)
    # ровно один replace prefix → asyncpg
    assert out.startswith('postgresql+asyncpg://')
    assert 'user:p@ss%40word@host/db' in out
