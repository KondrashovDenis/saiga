import os
from datetime import timedelta


def _required(name: str) -> str:
    """Достать env-переменную или упасть с понятной ошибкой при старте."""
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Environment variable {name} is required but not set. "
            f"Define it in web/.env (see web/.env.example)."
        )
    return val


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Секреты — обязательные. Никаких dev-fallback'ов в проде.
    SECRET_KEY = _required('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _required('DATABASE_URL')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─────────── Cookie / Session security ───────────
    # Caddy у нас auto-redirect на HTTPS, поэтому Secure безопасно.
    # SameSite=Lax — позволяет нормальные top-level навигации, но блокирует
    # большинство CSRF-атак с cross-origin POST.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)

    # ─────────── CSRF (Flask-WTF) ───────────
    # SECRET_KEY используется для подписи токенов.
    WTF_CSRF_TIME_LIMIT = None  # токен живёт пока активна сессия
    WTF_CSRF_SSL_STRICT = True

    # ─────────── Body size ───────────
    # 16MB hard-cap (file upload сам ограничивает 10MB, но Flask должен иметь
    # верхний предел чтобы не ловить медленный 100MB-pipe).
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # LLM API — внутри docker network к saiga-llm:5000
    LLM_API_URL = os.environ.get('LLM_API_URL', 'http://saiga-llm:5000/v1/chat/completions')
    LLM_DEFAULT_TEMPERATURE = float(os.environ.get('DEFAULT_TEMPERATURE', '0.7'))
    LLM_DEFAULT_TOP_P = float(os.environ.get('DEFAULT_TOP_P', '0.9'))
    LLM_DEFAULT_MAX_TOKENS = int(os.environ.get('DEFAULT_MAX_TOKENS', '2048'))

    # Telegram (для интеграции с ботом — авторизация через Telegram Login Widget)
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', 'saiga_ai_bot')

    # Sentry — опционально
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    SENTRY_ENV = os.environ.get('SENTRY_ENV', 'production')
    SENTRY_RELEASE = os.environ.get('SENTRY_RELEASE')

    # Rate limiting (Flask-Limiter)
    # Backend: redis://saiga-web-redis:6379/0 — отдельный контейнер на homeserver
    # (на debianOCR живёт saiga-bot-redis, к нему web не дотянется).
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'redis://saiga-web-redis:6379/0')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True

    # Лимиты
    MAX_CONVERSATIONS_PER_USER = 50
    MAX_MESSAGES_PER_CONVERSATION = 100
