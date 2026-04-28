"""ConversationHandler для in-bot редактирования настроек.

Юзер жмёт кнопку "🌡 Temperature" → бот спрашивает значение → юзер пишет число
→ бот валидирует, сохраняет в Setting, возвращает в меню настроек.

Toggle notifications — без conversation, immediate one-shot.
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
from sqlalchemy import select

from keyboards.settings import SettingsKeyboard
from models.database import async_session, get_or_create_user
from saiga_shared.models import Setting


logger = logging.getLogger(__name__)


# states
AWAIT_TEMPERATURE, AWAIT_TOP_P, AWAIT_MAX_TOKENS = range(3)


async def _get_or_create_setting(user_id: int) -> Setting:
    """Достаём Setting юзера или создаём дефолтный."""
    async with async_session() as session:
        stmt = select(Setting).where(Setting.user_id == user_id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()
        if s is None:
            s = Setting(user_id=user_id)
            session.add(s)
            await session.commit()
            await session.refresh(s)
    return s


async def _save_setting(user_id: int, **kwargs) -> Setting:
    """Атомарно обновить поля Setting юзера."""
    async with async_session() as session:
        stmt = select(Setting).where(Setting.user_id == user_id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()
        if s is None:
            s = Setting(user_id=user_id, **kwargs)
            session.add(s)
        else:
            for k, v in kwargs.items():
                setattr(s, k, v)
        await session.commit()
        await session.refresh(s)
        return s


# ───────────────────────── Temperature ─────────────────────────

async def ask_temperature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    s = await _get_or_create_setting(db_user.id)
    await q.message.reply_text(
        f"🌡 Введи новое значение <b>Temperature</b>.\n"
        f"Текущее: <b>{s.temperature}</b>\n"
        f"Диапазон: <code>0.1 — 2.0</code>\n"
        f"<i>0.1 — точно, 0.7 — баланс, 1.0 — креативно.</i>\n\n"
        f"/cancel чтобы отменить.",
        parse_mode="HTML",
    )
    return AWAIT_TEMPERATURE


async def receive_temperature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip().replace(",", "."))
        if not (0.1 <= v <= 2.0):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи число от 0.1 до 2.0. /cancel чтобы выйти.")
        return AWAIT_TEMPERATURE

    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    await _save_setting(db_user.id, temperature=v)
    await update.message.reply_text(
        f"✅ Temperature обновлён на <b>{v}</b>",
        parse_mode="HTML",
        reply_markup=SettingsKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


# ───────────────────────── Top P ─────────────────────────

async def ask_top_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    s = await _get_or_create_setting(db_user.id)
    await q.message.reply_text(
        f"🎯 Введи новое значение <b>Top P</b>.\n"
        f"Текущее: <b>{s.top_p}</b>\n"
        f"Диапазон: <code>0.1 — 1.0</code>\n"
        f"<i>Разнообразие словаря модели.</i>\n\n"
        f"/cancel чтобы отменить.",
        parse_mode="HTML",
    )
    return AWAIT_TOP_P


async def receive_top_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip().replace(",", "."))
        if not (0.1 <= v <= 1.0):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи число от 0.1 до 1.0. /cancel чтобы выйти.")
        return AWAIT_TOP_P

    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    await _save_setting(db_user.id, top_p=v)
    await update.message.reply_text(
        f"✅ Top P обновлён на <b>{v}</b>",
        parse_mode="HTML",
        reply_markup=SettingsKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


# ───────────────────────── Max Tokens ─────────────────────────

async def ask_max_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    s = await _get_or_create_setting(db_user.id)
    await q.message.reply_text(
        f"📊 Введи новое значение <b>Max Tokens</b>.\n"
        f"Текущее: <b>{s.max_tokens}</b>\n"
        f"Диапазон: <code>128 — 8192</code>\n"
        f"<i>Лимит длины ответа модели.</i>\n\n"
        f"/cancel чтобы отменить.",
        parse_mode="HTML",
    )
    return AWAIT_MAX_TOKENS


async def receive_max_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = int(update.message.text.strip())
        if not (128 <= v <= 8192):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи целое число от 128 до 8192. /cancel чтобы выйти.")
        return AWAIT_MAX_TOKENS

    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    await _save_setting(db_user.id, max_tokens=v)
    await update.message.reply_text(
        f"✅ Max Tokens обновлён на <b>{v}</b>",
        parse_mode="HTML",
        reply_markup=SettingsKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


# ───────────────────────── Cancel ─────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отменено.",
        reply_markup=SettingsKeyboard.get_keyboard(),
    )
    return ConversationHandler.END


# ───────────────────────── Toggle notifications (без conversation) ─────────

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    db_user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        telegram_username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    s = await _get_or_create_setting(db_user.id)
    new_state = not s.notifications_enabled
    await _save_setting(db_user.id, notifications_enabled=new_state)
    await q.edit_message_text(
        f"🔔 Уведомления теперь <b>{'включены' if new_state else 'выключены'}</b>.",
        parse_mode="HTML",
        reply_markup=SettingsKeyboard.get_keyboard(),
    )


# ───────────────────────── Handlers (для регистрации в main.py) ─────────

settings_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(ask_temperature, pattern="^set_temperature$"),
        CallbackQueryHandler(ask_top_p, pattern="^set_top_p$"),
        CallbackQueryHandler(ask_max_tokens, pattern="^set_max_tokens$"),
    ],
    states={
        AWAIT_TEMPERATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_temperature)],
        AWAIT_TOP_P: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_top_p)],
        AWAIT_MAX_TOKENS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_max_tokens)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    name="settings_edit",
    persistent=False,
)

toggle_notifications_handler = CallbackQueryHandler(
    toggle_notifications, pattern="^toggle_notifications$"
)
