"""Deep-link авторизация и привязка через Telegram-бота.

Старый flow на Telegram Login Widget удалён — он зависел от Widget JS,
кэшируется на стороне Telegram, ломается при смене domain в @BotFather.

Новый flow:
  1. Web создаёт одноразовый токен (kind='link' для привязки или 'login'
     для первичного входа), TTL 10 минут.
  2. Юзер открывает t.me/<bot>?start=<kind>_<token>.
  3. Бот ловит /start, ищет токен в БД, привязывает/логинит, ставит used_at.
  4. Web поллит status-endpoint и обновляет UI / выдаёт session-cookie.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user

from config import Config
from database import db
from extensions import limiter
from models.telegram_token import TelegramLinkToken
from models.user import User


telegram_auth_bp = Blueprint("telegram_auth", __name__, url_prefix="/api/telegram")


def _bot_url(token: str, kind: str) -> str:
    return f"https://t.me/{Config.TELEGRAM_BOT_USERNAME}?start={kind}_{token}"


# ───────────────────────── LINK (привязка для авторизованного юзера) ─────────

@telegram_auth_bp.route("/link/start", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def link_start():
    """Создаёт link-токен и возвращает t.me URL.

    Если у юзера уже привязан Telegram — возвращает 409.
    """
    if current_user.telegram_id is not None:
        return jsonify({
            "error": "telegram_already_linked",
            "telegram_username": current_user.telegram_username,
        }), 409

    tok = TelegramLinkToken.generate(kind="link", user_id=current_user.id)
    db.session.add(tok)
    db.session.commit()

    return jsonify({
        "url": _bot_url(tok.token, "link"),
        "expires_at": tok.expires_at.isoformat() + "Z",
    })


@telegram_auth_bp.route("/link/status", methods=["GET"])
@login_required
def link_status():
    """Возвращает текущее состояние привязки. UI поллит после link/start."""
    return jsonify({
        "linked": current_user.telegram_id is not None,
        "telegram_username": current_user.telegram_username,
        "telegram_id": current_user.telegram_id,
    })


@telegram_auth_bp.route("/unlink", methods=["POST"])
@login_required
@limiter.limit("5 per hour")
def unlink():
    """Отвязать Telegram. Запрет если это единственный способ входа."""
    if not current_user.can_login_with_password:
        return jsonify({
            "error": "telegram_is_only_auth",
            "message": "Нельзя отвязать — установи пароль сначала.",
        }), 400

    if current_user.unlink_telegram():
        db.session.commit()
        return jsonify({"linked": False})

    return jsonify({"error": "unlink_failed"}), 500


# ───────────────────────── LOGIN (первичный вход через Telegram) ─────────────

@telegram_auth_bp.route("/login/start", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour")
def login_start():
    """Создаёт login-токен (без user_id) для anonymous-юзера.

    Юзер открывает t.me URL, бот спрашивает подтверждение, по подтверждению
    создаёт/находит юзера по telegram_id и проставляет user_id в токен.

    NB: exempt от CSRF в app.py (anonymous endpoint, нет сессии для CSRF-токена).
    Защита от спама — rate-limit по IP.
    """
    tok = TelegramLinkToken.generate(kind="login", user_id=None)
    db.session.add(tok)
    db.session.commit()

    return jsonify({
        "url": _bot_url(tok.token, "login"),
        "token": tok.token,        # клиент использует его для poll
        "expires_at": tok.expires_at.isoformat() + "Z",
    })


@telegram_auth_bp.route("/login/status", methods=["GET"])
def login_status():
    """Поллится клиентом. Если бот заполнил user_id — выдаём session-cookie."""
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"error": "token_required"}), 400

    tok = db.session.query(TelegramLinkToken).filter_by(token=token, kind="login").first()
    if not tok:
        return jsonify({"error": "token_not_found"}), 404

    if tok.is_expired:
        return jsonify({"status": "expired"}), 410

    if tok.user_id is None:
        # Бот ещё не подтвердил вход.
        return jsonify({"status": "pending"})

    # Бот подтвердил — выдаём session-cookie.
    user = db.session.query(User).get(tok.user_id)
    if not user:
        return jsonify({"error": "user_not_found"}), 500

    # Помечаем токен использованным (если ещё не).
    if tok.used_at is None:
        tok.used_at = datetime.utcnow()
        db.session.commit()

    login_user(user, remember=True)
    session.permanent = True

    return jsonify({
        "status": "ok",
        "user_id": user.id,
        "display_name": user.display_name,
        "redirect": "/",
    })


# ───────────────────────── AUTO-LOGIN из бота (deep-link «Открыть в Web») ────

@telegram_auth_bp.route("/auto/<token>", methods=["GET"])
def auto_login(token):
    """Deep-link auto-login. Юзер жмёт в боте «🌐 Открыть в Web», бот
    создаёт токен kind='auto' с user_id=db_user.id (известен сразу,
    т.к. юзер уже идентифицирован Telegram-ом) и выдаёт URL
    https://saiga.vaibkod.ru/api/telegram/auto/<token>.

    Здесь: проверяем токен → login_user → redirect на /.

    SECURITY: токен в URL = bearer. Любой кто перехватит ссылку → залогинен.
    Защита:
      - TTL короткий (бот делает 5 мин)
      - Single-use (used_at)
      - Только HTTPS (Caddy форсит)
      - Логи в Sentry для аудита
    """
    from datetime import datetime
    from flask import redirect, current_app

    tok = db.session.query(TelegramLinkToken).filter_by(
        token=token, kind="auto").first()
    if tok is None:
        current_app.logger.warning("auto-login: token not found")
        return jsonify({"error": "token_not_found"}), 404
    if tok.is_expired:
        current_app.logger.info("auto-login: token expired (user_id=%s)", tok.user_id)
        return jsonify({"error": "expired"}), 410
    if tok.is_used:
        current_app.logger.warning("auto-login: token already used (user_id=%s)", tok.user_id)
        return jsonify({"error": "already_used"}), 410
    if tok.user_id is None:
        return jsonify({"error": "no_user_bound"}), 400

    user = User.query.get(tok.user_id) if hasattr(User, 'query') else \
           db.session.query(User).get(tok.user_id)
    if user is None:
        return jsonify({"error": "user_not_found"}), 500

    tok.used_at = datetime.utcnow()
    db.session.commit()

    login_user(user, remember=True)
    session.permanent = True
    current_app.logger.info("auto-login OK: user_id=%s (%s)", user.id, user.display_name)
    return redirect("/")
