"""Slash-команды бота: /help, /new, /list, /settings, /current, /rename."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes
from sqlalchemy import select

from keyboards.main_menu import MainMenuKeyboard
from keyboards.settings import SettingsKeyboard
from models.database import async_session, get_or_create_user
from saiga_shared.models import Conversation, Setting
from utils.conversation_manager import ConversationManager


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>Saiga AI — Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/new — новый диалог\n"
        "/list — мои диалоги\n"
        "/current — текущий активный диалог\n"
        "/rename <i>&lt;новое имя&gt;</i> — переименовать активный диалог\n"
        "/settings — настройки\n"
        "/help — эта справка\n\n"
        "<b>Что умею:</b>\n"
        "• Отвечать на текстовые сообщения\n"
        "• Голосовые (распознавание)\n"
        "• Документы (PDF, DOCX)\n"
        "• Кнопки быстрых ответов после реплики\n\n"
        "Веб-версия: <code>saiga.vaibkod.ru</code> — все диалоги общие."
    )
    await update.message.reply_text(text, parse_mode='HTML')


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversation = await ConversationManager.create_new_conversation(db_user.id)
    context.user_data['active_conversation_id'] = conversation.id
    await update.message.reply_text(
        f"💬 Создан новый диалог #{conversation.id}.\n\n"
        f"Напиши что-нибудь — диалог получит имя автоматически по первому сообщению. "
        f"Или переименуй вручную: <code>/rename Моё название</code>",
        parse_mode='HTML',
        reply_markup=MainMenuKeyboard.get_quick_replies(),
    )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversations = await ConversationManager.get_user_conversations(db_user.id)

    active_id = context.user_data.get('active_conversation_id') if context.user_data else None

    if not conversations:
        await update.message.reply_text(
            "📋 У тебя пока нет диалогов. /new чтобы создать."
        )
        return

    text = "📋 <b>Твои диалоги:</b>\n\nВыбери диалог чтобы продолжить:\n\n"
    keyboard = []
    for conv in conversations:
        message_count = len(conv.messages) if conv.messages else 0
        title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv.id}"
        marker = "🟢 " if conv.id == active_id else ""  # активный диалог
        button_text = f"{marker}💬 {title} ({message_count})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_conv_{conv.id}")])
    keyboard.append([InlineKeyboardButton("➕ Новый диалог", callback_data="new_conversation")])

    await update.message.reply_text(
        text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает РЕАЛЬНЫЕ настройки юзера + кнопки редактирования."""
    user = update.effective_user
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )

    async with async_session() as session:
        stmt = select(Setting).where(Setting.user_id == db_user.id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()

    if s is None:
        text = "⚙️ Настроек пока нет — будут созданы автоматически после первого сообщения."
    else:
        notif = "включены" if s.notifications_enabled else "выключены"
        text = (
            "⚙️ <b>Настройки</b>\n\n"
            f"🌡 Temperature: <b>{s.temperature}</b>  <i>(точность ↔ креатив)</i>\n"
            f"🎯 Top P: <b>{s.top_p}</b>  <i>(разнообразие словаря)</i>\n"
            f"📊 Max Tokens: <b>{s.max_tokens}</b>  <i>(лимит длины ответа)</i>\n"
            f"🔔 Уведомления: <b>{notif}</b>\n\n"
            "Жми кнопку чтобы изменить."
        )

    await update.message.reply_text(text, parse_mode='HTML', reply_markup=SettingsKeyboard.get_keyboard())


async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущий активный диалог."""
    user = update.effective_user
    active_id = context.user_data.get('active_conversation_id') if context.user_data else None
    if not active_id:
        await update.message.reply_text(
            "Активного диалога нет. /new чтобы создать или /list чтобы выбрать."
        )
        return

    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversations = await ConversationManager.get_user_conversations(db_user.id)
    conv = next((c for c in conversations if c.id == active_id), None)
    if not conv:
        context.user_data.pop('active_conversation_id', None)
        await update.message.reply_text("Активный диалог не найден (возможно, удалён). /list")
        return

    title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv.id}"
    msg_count = len(conv.messages) if conv.messages else 0
    await update.message.reply_text(
        f"🟢 Активный: <b>{title}</b>\n"
        f"💬 Сообщений: {msg_count}\n"
        f"📅 Обновлён: {conv.updated_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<code>/rename новое имя</code> — переименовать.",
        parse_mode='HTML',
    )


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """`/rename <новое имя>` — переименовать активный диалог."""
    user = update.effective_user
    active_id = context.user_data.get('active_conversation_id') if context.user_data else None
    if not active_id:
        await update.message.reply_text(
            "Активного диалога нет. /list чтобы выбрать или /new чтобы создать."
        )
        return

    new_title = " ".join(context.args or []).strip()
    if not new_title:
        await update.message.reply_text(
            "Использование: <code>/rename Моё новое название</code>",
            parse_mode='HTML',
        )
        return
    if len(new_title) > 200:
        new_title = new_title[:200]

    # Проверяем что юзер — владелец диалога, потом обновляем title.
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    async with async_session() as session:
        stmt = select(Conversation).where(
            Conversation.id == active_id,
            Conversation.user_id == db_user.id,
        )
        result = await session.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            await update.message.reply_text("❌ Диалог не найден или не принадлежит тебе.")
            return
        conv.title = new_title
        await session.commit()

    await update.message.reply_text(f"✅ Переименован в: <b>{new_title}</b>", parse_mode='HTML')


command_handlers = [
    CommandHandler('help', help_command),
    CommandHandler('new', new_command),
    CommandHandler('list', list_command),
    CommandHandler('settings', settings_command),
    CommandHandler('current', current_command),
    CommandHandler('rename', rename_command),
]
