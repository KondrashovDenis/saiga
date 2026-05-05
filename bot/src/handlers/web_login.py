"""Команда /web и callback web_login_request — выдаёт юзеру deep-link
для auto-login в saiga.vaibkod.ru без ввода пароля.

Бот создаёт TelegramLinkToken kind='auto' с user_id=db_user.id (юзер уже
идентифицирован Telegram-ом), выдаёт URL вида
https://saiga.vaibkod.ru/api/telegram/auto/<token>. По нему web сразу
логинит и редиректит на /.

SECURITY: токен в URL = bearer. Защита:
  - TTL 5 минут
  - Single-use (web ставит used_at)
  - Только HTTPS
  - Кнопка «Открыть» отправляется как обычное сообщение, не как
    inline-кнопка с URL (юзер жмёт сам и видит куда идёт)
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from models.database import async_session, get_or_create_user
from saiga_shared.models import TelegramLinkToken


logger = logging.getLogger(__name__)


WEB_BASE_URL = "https://saiga.vaibkod.ru"
TTL_MINUTES = 5


async def _create_auto_token(tg_user) -> str:
    """Создать одноразовый auto-токен для текущего TG-юзера, вернуть URL."""
    db_user = await get_or_create_user(
        telegram_id=tg_user.id,
        telegram_username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    async with async_session() as session:
        tok = TelegramLinkToken.generate(kind="auto", user_id=db_user.id, ttl_minutes=TTL_MINUTES)
        session.add(tok)
        await session.commit()
        await session.refresh(tok)

    logger.info("auto-login token created for user_id=%s (tg_id=%s)", db_user.id, tg_user.id)
    return f"{WEB_BASE_URL}/api/telegram/auto/{tok.token}"


def _build_message_and_keyboard(url: str) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "🌐 <b>Открыть Saiga в браузере</b>\n\n"
        "Жми кнопку — попадёшь сразу в свой аккаунт без ввода пароля.\n"
        "<i>Ссылка одноразовая, живёт 5 минут.</i>"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Открыть в Web", url=url)]])
    return text, keyboard


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/web → выдать ссылку для auto-login."""
    url = await _create_auto_token(update.effective_user)
    text, kb = _build_message_and_keyboard(url)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def web_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline-кнопка "🌐 Открыть в Web" из меню Settings."""
    q = update.callback_query
    await q.answer()
    url = await _create_auto_token(update.effective_user)
    text, kb = _build_message_and_keyboard(url)
    await q.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


web_command_handler = CommandHandler("web", web_command)
web_callback_handler = CallbackQueryHandler(web_callback, pattern="^web_login_request$")
