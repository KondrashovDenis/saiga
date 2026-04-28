"""Тесты на TelegramLinkToken — модель из shared.

Покрывают:
  - generate() с валидным kind и невалидным
  - is_expired при старом expires_at
  - is_used при заполненном used_at
  - is_valid: только если не expired И не used
"""
from datetime import datetime, timedelta

import pytest

from saiga_shared.models import TelegramLinkToken


def test_generate_link_token():
    tok = TelegramLinkToken.generate(kind="link", user_id=42)
    assert tok.kind == "link"
    assert tok.user_id == 42
    assert tok.token  # есть строка
    assert len(tok.token) >= 20  # secrets.token_urlsafe(24) ≥ 32 base64
    assert tok.expires_at > datetime.utcnow()
    assert tok.used_at is None


def test_generate_login_token_no_user():
    tok = TelegramLinkToken.generate(kind="login", user_id=None)
    assert tok.kind == "login"
    assert tok.user_id is None
    assert tok.is_valid is True


def test_generate_unique_tokens():
    """Два сгенерированных токена не должны совпадать."""
    a = TelegramLinkToken.generate(kind="link", user_id=1)
    b = TelegramLinkToken.generate(kind="link", user_id=1)
    assert a.token != b.token


def test_generate_invalid_kind():
    with pytest.raises(ValueError, match="Unknown kind"):
        TelegramLinkToken.generate(kind="bogus", user_id=1)


def test_is_expired_true_when_past():
    tok = TelegramLinkToken.generate(kind="link", user_id=1)
    tok.expires_at = datetime.utcnow() - timedelta(seconds=1)
    assert tok.is_expired is True
    assert tok.is_valid is False


def test_is_expired_false_when_future():
    tok = TelegramLinkToken.generate(kind="link", user_id=1, ttl_minutes=10)
    assert tok.is_expired is False


def test_is_used_when_used_at_set():
    tok = TelegramLinkToken.generate(kind="link", user_id=1)
    assert tok.is_used is False
    tok.used_at = datetime.utcnow()
    assert tok.is_used is True
    assert tok.is_valid is False


def test_is_valid_requires_both():
    """is_valid: только если не expired И не used."""
    tok = TelegramLinkToken.generate(kind="link", user_id=1, ttl_minutes=10)
    assert tok.is_valid is True

    # Истёк.
    tok.expires_at = datetime.utcnow() - timedelta(seconds=1)
    assert tok.is_valid is False

    # Истёк И использован.
    tok.used_at = datetime.utcnow()
    assert tok.is_valid is False

    # Использован но не истёк.
    tok.expires_at = datetime.utcnow() + timedelta(minutes=10)
    assert tok.is_valid is False  # used_at всё равно блокирует


def test_repr_truncates_token():
    tok = TelegramLinkToken.generate(kind="link", user_id=99)
    r = repr(tok)
    assert "link" in r
    assert "user=99" in r
    # Полный токен НЕ должен быть в repr — только первые 8 символов.
    assert tok.token not in r


def test_ttl_minutes_param():
    """ttl_minutes управляет временем жизни."""
    short = TelegramLinkToken.generate(kind="link", user_id=1, ttl_minutes=1)
    long = TelegramLinkToken.generate(kind="link", user_id=1, ttl_minutes=30)
    delta = long.expires_at - short.expires_at
    # ~29 минут разницы (с учётом ms дрейфа на разных вызовах).
    assert delta > timedelta(minutes=28)
