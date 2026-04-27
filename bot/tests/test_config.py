"""Тесты валидации обязательных env-переменных.

Принцип fail-fast: бот не должен стартовать с пустыми обязательными секретами,
он должен сразу ясно сказать какая переменная не задана.
"""

import pytest

from config import _required


def test_required_returns_value(monkeypatch):
    """Когда env-переменная задана — возвращаем её значение."""
    monkeypatch.setenv('SAIGA_TEST_VAR', 'hello')
    assert _required('SAIGA_TEST_VAR') == 'hello'


def test_required_raises_when_missing(monkeypatch):
    """Когда env-переменная отсутствует — кидаем RuntimeError с понятным сообщением."""
    monkeypatch.delenv('SAIGA_TEST_VAR', raising=False)
    with pytest.raises(RuntimeError, match='SAIGA_TEST_VAR'):
        _required('SAIGA_TEST_VAR')


def test_required_raises_when_empty_string(monkeypatch):
    """Пустая строка тоже не должна проходить — это часто опечатка в .env."""
    monkeypatch.setenv('SAIGA_TEST_VAR', '')
    with pytest.raises(RuntimeError, match='SAIGA_TEST_VAR'):
        _required('SAIGA_TEST_VAR')


def test_required_message_mentions_env_file():
    """Сообщение должно подсказывать куда смотреть. Запускаем _required для
    несуществующей переменной и проверяем текст исключения."""
    try:
        _required('THIS_VAR_DEFINITELY_DOES_NOT_EXIST_XYZ123')
    except RuntimeError as e:
        msg = str(e)
        assert 'THIS_VAR_DEFINITELY_DOES_NOT_EXIST_XYZ123' in msg
        assert '.env' in msg.lower()
    else:
        pytest.fail("Expected RuntimeError, got nothing")
