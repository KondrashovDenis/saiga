"""Singleton-инстансы расширений Flask, которые нужны нескольким модулям.

Объявлены здесь, инициализируются в app.py через init_app(). Это снимает
циклические импорты вроде "routes импортит limiter, app.py импортит routes".
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Rate limiter — backend Redis (см. RATELIMIT_STORAGE_URI в config.py).
# Для авторизованных юзеров применяем лимиты по user.id, для anonymous — по IP.
def _key_func():
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()


limiter = Limiter(
    key_func=_key_func,
    default_limits=["1000 per hour"],   # широкий дефолт; конкретные лимиты — на эндпоинтах
    headers_enabled=True,
)
