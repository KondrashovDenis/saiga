"""ConversationHandler для /new — спрашивает имя диалога перед созданием.

Паритет с web /conversations/new где есть форма title. До этого /new
сразу создавал диалог с дефолтом "Новый диалог", и потом auto-rename
из первого user-сообщения. Теперь юзер может задать имя сразу.

Вход:
  - команда /new
  - inline-кнопка "💬 Новый диалог" (callback_data="new_conversation")

Поведение:
  - бот спрашивает имя: <текст> или /skip (auto-rename из первого сообщения)
  - принимает 1–200 символов
  - создаёт Conversation, ставит active в context.user_data
"""
import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager
from keyboards.main_menu import MainMenuKeyboard


logger = logging.getLogger(__name__)


AWAIT_TITLE = 1


def _activate_conversation(context, conv_id: int) -> None:
    if context.user_data is None:
        return
    context.user_data['active_conversation_id'] = conv_id


async def _ask_title(reply_func) -> int:
    await reply_func(
        "💬 Как назвать новый диалог?\n\n"
        "Напиши название (1–200 символов) или отправь /skip — тогда диалог "
        "получит имя автоматически по первому твоему сообщению."
    )
    return AWAIT_TITLE


async def new_via_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/new → спросить имя."""
    return await _ask_title(update.message.reply_text)


async def new_via_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline-кнопка «Новый диалог» → ack callback + спросить имя."""
    q = update.callback_query
    await q.answer()
    return await _ask_title(q.message.reply_text)


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принять имя от юзера, создать диалог."""
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text("Пустое имя. Введи ещё раз или /skip.")
        return AWAIT_TITLE
    if title.startswith("/"):
        await update.message.reply_text("Имя не должно начинаться с / — это похоже на команду.")
        return AWAIT_TITLE
    if len(title) > 200:
        title = title[:200]

    user = update.effective_user
    db_user = await get_or_create_user(
        telegram_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    conv = await ConversationManager.create_new_conversation(db_user.id, title=title)
    _activate_conversation(context, conv.id)

    logger.info("new conversation #%s (user_id=%s, title=%r)", conv.id, db_user.id, title)
    await update.message.reply_text(
        f"💬 Создан диалог <b>{title}</b> (#{conv.id}).\n\nПиши — буду отвечать.",
        parse_mode="HTML",
        reply_markup=MainMenuKeyboard.get_quick_replies(),
    )
    return ConversationHandler.END


async def skip_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/skip → создать с дефолтным именем (auto-rename сработает позже)."""
    user = update.effective_user
    db_user = await get_or_create_user(
        telegram_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    conv = await ConversationManager.create_new_conversation(db_user.id)
    _activate_conversation(context, conv.id)

    logger.info("new conversation #%s (user_id=%s, no-title)", conv.id, db_user.id)
    await update.message.reply_text(
        f"💬 Диалог #{conv.id} создан без имени — переименуется по первому "
        f"твоему сообщению. Пиши.",
        reply_markup=MainMenuKeyboard.get_quick_replies(),
    )
    return ConversationHandler.END


async def cancel_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отменено. Диалог не создан.",
        reply_markup=MainMenuKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


new_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler("new", new_via_command),
        CallbackQueryHandler(new_via_callback, pattern="^new_conversation$"),
    ],
    states={
        AWAIT_TITLE: [
            CommandHandler("skip", skip_title),
            CommandHandler("cancel", cancel_new),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_new)],
    name="new_conversation",
    persistent=False,
)
