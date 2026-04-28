"""
/start handler. Поддерживает три варианта:

  /start                        — обычный вход в чат с ботом
  /start link_<token>           — привязать TG к существующему web-юзеру
  /start login_<token>          — войти в web через TG (deep-link)

Токены живут в таблице telegram_link_tokens (см. saiga_shared.models).
"""
from datetime import datetime
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from sqlalchemy import select

from models.database import async_session
from models.user import User
from models.setting import Setting
from models.telegram_token import TelegramLinkToken
from keyboards.main_menu import MainMenuKeyboard

logger = logging.getLogger(__name__)


WELCOME_NEW = """
🤖 Добро пожаловать в Saiga AI, {name}!

Я - ваш персональный AI-ассистент на основе языковой модели Saiga Nemo 12B.

🔥 **Мои возможности:**
• 💬 Ведение диалогов на любые темы
• 📚 Помощь с учебой и работой
• 🧠 Решение задач и объяснения
• 📄 Анализ документов
• 🎤 Обработка голосовых сообщений

📋 **Основные команды:**
/new - Начать новый диалог
/list - Мои диалоги
/settings - Настройки
/help - Помощь

Просто напишите мне сообщение, и мы начнем общаться! 🚀
"""

WELCOME_BACK = "👋 С возвращением, {name}!\n\nГотов продолжить наше общение. Что вас интересует?"


async def _ensure_user(session, tg_user):
    """Найти юзера по telegram_id, или создать нового."""
    stmt = select(User).where(User.telegram_id == tg_user.id)
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user is None:
        db_user = User(
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code or "ru",
            auth_method="telegram",
        )
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        settings = Setting(user_id=db_user.id)
        session.add(settings)
        await session.commit()

        logger.info("Новый пользователь: %s (@%s)", tg_user.full_name, tg_user.username)
        return db_user, True

    return db_user, False


async def _load_valid_token(session, token: str, kind: str) -> TelegramLinkToken | None:
    """Найти токен по строке. Возвращает None если нет / истёк / уже использован."""
    stmt = select(TelegramLinkToken).where(
        TelegramLinkToken.token == token,
        TelegramLinkToken.kind == kind,
    )
    result = await session.execute(stmt)
    tok = result.scalar_one_or_none()
    if tok is None:
        return None
    if tok.is_expired or tok.is_used:
        return None
    return tok


async def _handle_link(update: Update, session, tg_user, token_str: str):
    """Привязать TG к существующему web-юзеру."""
    tok = await _load_valid_token(session, token_str, "link")
    if tok is None:
        await update.message.reply_text(
            "❌ Ссылка для привязки недействительна или истекла. "
            "Запроси новую в веб-интерфейсе."
        )
        return

    # Проверяем — не привязан ли этот TG уже к другому юзеру.
    existing_stmt = select(User).where(User.telegram_id == tg_user.id)
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None and existing.id != tok.user_id:
        await update.message.reply_text(
            f"❌ Этот Telegram уже привязан к другому аккаунту "
            f"(`{existing.display_name}`). Отвяжи там сначала.",
            parse_mode="Markdown",
        )
        return

    # Получаем целевого юзера и привязываем.
    target = await session.get(User, tok.user_id)
    if target is None:
        await update.message.reply_text("❌ Аккаунт для привязки не найден.")
        return

    target.link_telegram(
        telegram_id=tg_user.id,
        telegram_username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    target.last_activity = datetime.utcnow()
    tok.used_at = datetime.utcnow()
    await session.commit()

    logger.info("TG link: user_id=%s ↔ tg_id=%s", target.id, tg_user.id)
    await update.message.reply_text(
        f"✅ Аккаунт `{target.display_name}` успешно привязан!\n"
        f"Возвращайся в веб — там уже видно привязку.",
        parse_mode="Markdown",
        reply_markup=MainMenuKeyboard.get_keyboard(),
    )


async def _handle_login(update: Update, session, tg_user, token_str: str):
    """Завершить web-логин через TG (создать юзера если нет, заполнить token.user_id)."""
    tok = await _load_valid_token(session, token_str, "login")
    if tok is None:
        await update.message.reply_text(
            "❌ Ссылка для входа недействительна или истекла. "
            "Запроси новую в веб-интерфейсе."
        )
        return

    db_user, created = await _ensure_user(session, tg_user)

    tok.user_id = db_user.id
    tok.used_at = datetime.utcnow()
    db_user.last_activity = datetime.utcnow()
    await session.commit()

    logger.info("TG login: user_id=%s tg_id=%s (created=%s)", db_user.id, tg_user.id, created)
    msg = "✅ Вход подтверждён, возвращайся в браузер — ты залогинен."
    if created:
        msg += "\n\nДля тебя создан новый аккаунт. Все диалоги в боте и в вебе будут общими."
    await update.message.reply_text(msg, reply_markup=MainMenuKeyboard.get_keyboard())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с поддержкой deep-link."""
    tg_user = update.effective_user
    args = context.args or []
    arg = args[0] if args else ""

    async with async_session() as session:
        # Deep-link сценарии — НЕ создают юзера автоматически до проверки токена.
        if arg.startswith("link_"):
            await _handle_link(update, session, tg_user, arg[len("link_"):])
            return
        if arg.startswith("login_"):
            await _handle_login(update, session, tg_user, arg[len("login_"):])
            return

        # Обычный /start без аргументов — старое поведение.
        db_user, created = await _ensure_user(session, tg_user)

    text = (WELCOME_NEW if created else WELCOME_BACK).format(name=tg_user.first_name)
    await update.message.reply_text(text, reply_markup=MainMenuKeyboard.get_keyboard())


start_handler = CommandHandler("start", start_command)
