"""Отправка email через SMTP (Yandex / любой другой) + signed-token utils.

Конфиг через env:
  SMTP_HOST=smtp.yandex.ru
  SMTP_PORT=465
  SMTP_USE_SSL=true
  SMTP_USER=denciaopin@yandex.ru
  SMTP_PASSWORD=<app password из Яндекс ID>
  SMTP_FROM=denciaopin@yandex.ru   # обычно совпадает с SMTP_USER
  EMAIL_VERIFY_BASE_URL=https://saiga.vaibkod.ru   # для confirm-link

Если SMTP_HOST не задан — отправка no-op (логируется warning).
Это позволяет деплоить инфраструктуру без работающего SMTP, и включать его
позже сменой env.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import Config

logger = logging.getLogger(__name__)

# 24 часа на подтверждение email
EMAIL_TOKEN_TTL_SEC = 24 * 3600
EMAIL_TOKEN_SALT = "email-verify-v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt=EMAIL_TOKEN_SALT)


def make_verify_token(user_id: int, email: str) -> str:
    """Генерирует подписанный токен (HMAC-SHA1 + timestamp).

    Привязан к user_id И email — если юзер сменит email, старый токен
    невалиден.
    """
    return _serializer().dumps({"uid": user_id, "email": email})


def parse_verify_token(token: str) -> tuple[int | None, str | None]:
    """Возвращает (user_id, email) если токен валиден и не протух, иначе (None, None)."""
    try:
        data = _serializer().loads(token, max_age=EMAIL_TOKEN_TTL_SEC)
        return data.get("uid"), data.get("email")
    except SignatureExpired:
        logger.info("email verify token expired")
        return None, None
    except BadSignature:
        logger.warning("email verify token bad signature")
        return None, None


def is_smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER")
                and os.environ.get("SMTP_PASSWORD"))


def send_verify_email(to_email: str, username: str, verify_url: str) -> bool:
    """Отправить письмо с verify-ссылкой. True если ушло, False иначе.

    При SMTP_HOST=NONE логирует warning и возвращает True (для dev / локалки —
    юзер регистрируется без верификации). В production это место не
    срабатывает, потому что login-flow проверяет needs_email_verification.
    """
    if not is_smtp_configured():
        logger.warning("SMTP not configured — skipping verify email to %s. "
                       "Verify URL would be: %s", to_email, verify_url)
        return False

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "true").lower() in ("true", "1", "yes")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    msg = EmailMessage()
    msg["Subject"] = "Подтвердите регистрацию в Saiga AI"
    msg["From"] = f"Saiga AI <{smtp_from}>"
    msg["To"] = to_email

    text_body = (
        f"Привет, {username}!\n\n"
        f"Кто-то зарегистрировался в Saiga AI с этим email-адресом. "
        f"Чтобы подтвердить, открой ссылку (действует 24 часа):\n\n"
        f"{verify_url}\n\n"
        f"Если это не ты — просто проигнорируй это письмо, аккаунт не активируется.\n\n"
        f"— Saiga AI · saiga.vaibkod.ru"
    )

    html_body = f"""
    <html><body style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h2 style="color: #229ED9;">Подтверждение регистрации</h2>
      <p>Привет, <b>{username}</b>!</p>
      <p>Кто-то зарегистрировался в Saiga AI с этим email-адресом. Чтобы подтвердить, нажми на кнопку (ссылка действует 24 часа):</p>
      <p style="text-align: center; margin: 32px 0;">
        <a href="{verify_url}"
           style="background: #229ED9; color: white; padding: 12px 32px; text-decoration: none; border-radius: 6px; display: inline-block;">
           Подтвердить email
        </a>
      </p>
      <p style="color: #888; font-size: 13px;">
        Или открой ссылку вручную:<br>
        <span style="word-break: break-all;">{verify_url}</span>
      </p>
      <p style="color: #888; font-size: 13px;">
        Если это не ты — просто проигнорируй это письмо, аккаунт не активируется.
      </p>
      <p style="color: #888; font-size: 12px; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">
        — Saiga AI · <a href="https://saiga.vaibkod.ru">saiga.vaibkod.ru</a>
      </p>
    </body></html>
    """

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        ctx = ssl.create_default_context()
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=15) as s:
                s.login(smtp_user, smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                s.starttls(context=ctx)
                s.login(smtp_user, smtp_password)
                s.send_message(msg)
        logger.info("verify email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("SMTP send failed for %s: %s", to_email, e, exc_info=True)
        return False
