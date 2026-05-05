"""ConversationHandler: спросить имя у нового TG-юзера.

Зачем: если у юзера в Telegram нет first_name (приватный профиль или нечем
заполнить) — мы получаем User с пустым first_name. В админке его не отличить,
и delete-confirm требует ввода `tg-{id}` вместо человеческого имени.

Когда срабатывает: команда /name (или triggered из start_command если
db_user.first_name отсутствует — см. start.py).

Состояния: AWAIT_NAME → юзер вводит текст → пишем в users.first_name → END.
"""
import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from sqlalchemy import select

from models.database import async_session
from saiga_shared.models import User
from keyboards.main_menu import MainMenuKeyboard


logger = logging.getLogger(__name__)


AWAIT_NAME = 1


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: спросить имя. Если юзера нет в БД — создаст за нас обычный flow."""
    tg_user = update.effective_user
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == tg_user.id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()
        current_name = (db_user.first_name if db_user else None) or "пока не задано"

    await update.message.reply_text(
        f"Как мне к тебе обращаться?\n\n"
        f"Сейчас: <b>{current_name}</b>\n\n"
        f"Напиши имя одним сообщением (1–50 символов) или /cancel чтобы оставить как есть.",
        parse_mode="HTML",
    )
    return AWAIT_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("Пустое имя не подходит. Введи ещё раз или /cancel.")
        return AWAIT_NAME
    if len(name) > 50:
        await update.message.reply_text("Слишком длинное (максимум 50). Введи короче или /cancel.")
        return AWAIT_NAME
    # Не принимаем сообщения которые выглядят как команды.
    if name.startswith("/"):
        await update.message.reply_text("Имя не должно начинаться с / — это похоже на команду.")
        return AWAIT_NAME

    tg_user = update.effective_user
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == tg_user.id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user is None:
            await update.message.reply_text(
                "Аккаунт не найден. Сначала отправь /start чтобы создать его."
            )
            return ConversationHandler.END
        db_user.first_name = name
        await session.commit()

    logger.info("first_name set for tg_id=%s → %s", tg_user.id, name)
    await update.message.reply_text(
        f"✅ Записал. Буду звать тебя <b>{name}</b>.",
        parse_mode="HTML",
        reply_markup=MainMenuKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Окей, оставил как есть.",
        reply_markup=MainMenuKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


name_setup_handler = ConversationHandler(
    entry_points=[CommandHandler("name", ask_name)],
    states={
        AWAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    name="name_setup",
    persistent=False,
)
