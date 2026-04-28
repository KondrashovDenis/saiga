"""Inline-button callback handler.

Структура: единая функция button_callback маршрутизирует по data-префиксу.
Длинные ветки вынесены в отдельные хелперы внизу файла.
"""
import logging
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from sqlalchemy import select, delete

from keyboards.main_menu import MainMenuKeyboard
from keyboards.settings import SettingsKeyboard
from models.database import async_session, get_or_create_user
from saiga_shared.models import Conversation, Message, Setting
from utils.conversation_manager import ConversationManager
from handlers.text_handler import process_user_message


logger = logging.getLogger(__name__)


# ───────────────────────── Quick replies map ─────────────────────────
QUICK_REPLIES = {
    "quick_continue": "Продолжи",
    "quick_explain": "Поясни подробнее",
    "quick_example": "Дай пример",
    "quick_what": "Что это значит?",
}


# ───────────────────────── Main router ─────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    if data == "new_conversation":
        await _new_conversation(query, user, context)
    elif data == "list_conversations":
        await show_conversations_list(query, user)
    elif data == "back_to_list":
        await show_conversations_list(query, user)
    elif data.startswith("select_conv_"):
        await _select_conversation(query, user, int(data.replace("select_conv_", "")))
    elif data.startswith("show_history_"):
        await _show_history(query, user, int(data.replace("show_history_", "")))
    elif data.startswith("confirm_delete_"):
        await _confirm_delete(query, user, int(data.replace("confirm_delete_", "")))
    elif data.startswith("delete_confirmed_"):
        await _delete_confirmed(query, user, context, int(data.replace("delete_confirmed_", "")))
    elif data == "settings":
        await _show_settings(query, user)
    elif data == "help":
        await _show_help(query)
    elif data == "main_menu":
        await query.edit_message_text(
            "🤖 Главное меню\n\nВыберите нужное действие:",
            reply_markup=MainMenuKeyboard.get_keyboard(),
        )
    elif data in QUICK_REPLIES:
        # Заменяем callback на отправку обычного сообщения в LLM.
        text = QUICK_REPLIES[data]
        # query.message — последнее сообщение бота с кнопками. Отвечаем в тот же чат.
        await process_user_message(
            message=query.message,
            context=context,
            tg_user=user,
            text=text,
            telegram_message_id=None,
        )
    else:
        # set_temperature/set_top_p/set_max_tokens перехватывает
        # settings_conversation_handler, toggle_notifications — отдельный
        # CallbackQueryHandler. Здесь fallback на неизвестное.
        await query.edit_message_text(
            f"Неизвестная команда: {data}",
            reply_markup=MainMenuKeyboard.get_keyboard(),
        )


# ───────────────────────── Conversations ─────────────────────────

async def _new_conversation(query, user, context):
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversation = await ConversationManager.create_new_conversation(db_user.id)
    context.user_data['active_conversation_id'] = conversation.id
    await query.edit_message_text(
        f"💬 Создан новый диалог #{conversation.id}!\n\nНапиши что-нибудь — после первого сообщения "
        f"диалог получит имя автоматически.",
        reply_markup=MainMenuKeyboard.get_quick_replies(),
    )


async def show_conversations_list(query, user):
    """Список диалогов юзера. Если пусто — предлагаем создать."""
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversations = await ConversationManager.get_user_conversations(db_user.id)

    if not conversations:
        await query.edit_message_text(
            "📋 У тебя пока нет диалогов.\n\nИспользуй кнопку «Новый диалог» чтобы начать.",
            reply_markup=MainMenuKeyboard.get_keyboard(),
        )
        return

    text = "📋 <b>Твои диалоги:</b>\n\nВыбери диалог чтобы продолжить:\n\n"
    keyboard = []
    for conv in conversations:
        message_count = len(conv.messages) if conv.messages else 0
        title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv.id}"
        button_text = f"💬 {title} ({message_count})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_conv_{conv.id}")])
    keyboard.append([InlineKeyboardButton("➕ Новый диалог", callback_data="new_conversation")])
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="main_menu")])

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def _select_conversation(query, user, conv_id: int):
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversations = await ConversationManager.get_user_conversations(db_user.id)
    conv = next((c for c in conversations if c.id == conv_id), None)
    if not conv:
        await query.edit_message_text("❌ Диалог не найден.", reply_markup=MainMenuKeyboard.get_keyboard())
        return

    title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv_id}"
    message_count = len(conv.messages) if conv.messages else 0
    text = (
        f"📖 <b>{title}</b>\n\n"
        f"💬 Сообщений: {message_count}\n"
        f"📅 Обновлён: {conv.updated_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Просто пиши — буду отвечать в этом диалоге."
    )
    keyboard = [
        [InlineKeyboardButton("📋 История диалога", callback_data=f"show_history_{conv_id}")],
        [InlineKeyboardButton("🔙 К списку диалогов", callback_data="back_to_list")],
    ]
    # Делаем выбранный диалог активным.
    # context недоступен в этой функции напрямую — но select эффективно нужен только для UI;
    # активный diff будет проставлен при первом следующем сообщении в process_user_message.
    # Если хочется явно — пробрасывай context из caller'а.
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_history(query, user, conv_id: int):
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    messages = await ConversationManager.get_conversation_messages(conv_id)

    if not messages:
        text = "📭 В этом диалоге пока нет сообщений."
    else:
        conversations = await ConversationManager.get_user_conversations(db_user.id)
        conv = next((c for c in conversations if c.id == conv_id), None)
        title = (conv.title if conv and conv.title and conv.title != "Новый диалог"
                 else f"Диалог #{conv_id}")
        text = f"📋 <b>История: {title}</b>\n\n"
        recent = messages[-10:] if len(messages) > 10 else messages
        if len(messages) > 10:
            text += f"<i>(последние 10 из {len(messages)})</i>\n\n"
        for msg in recent:
            if msg.role == 'user':
                text += f"👤 <b>Ты:</b> {msg.content}\n\n"
            else:
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                text += f"🤖 <b>Saiga:</b> {content}\n\n"
            if len(text) > 3500:
                text += "<i>...обрезано</i>"
                break

    keyboard = [
        [InlineKeyboardButton("🔙 К диалогу", callback_data=f"select_conv_{conv_id}")],
        [InlineKeyboardButton("🗑 Удалить диалог", callback_data=f"confirm_delete_{conv_id}")],
        [InlineKeyboardButton("📋 К списку", callback_data="back_to_list")],
    ]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def _confirm_delete(query, user, conv_id: int):
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )
    conversations = await ConversationManager.get_user_conversations(db_user.id)
    conv = next((c for c in conversations if c.id == conv_id), None)
    if not conv:
        await query.edit_message_text("❌ Диалог не найден.", reply_markup=MainMenuKeyboard.get_keyboard())
        return

    title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv_id}"
    text = (
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить диалог <b>{title}</b>?\n"
        f"💬 Сообщений: {len(conv.messages) if conv.messages else 0}\n\n"
        "Это действие нельзя отменить."
    )
    keyboard = [[
        InlineKeyboardButton("✅ Удалить", callback_data=f"delete_confirmed_{conv_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"show_history_{conv_id}"),
    ]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def _delete_confirmed(query, user, context, conv_id: int):
    try:
        async with async_session() as session:
            await session.execute(delete(Message).where(Message.conversation_id == conv_id))
            await session.execute(delete(Conversation).where(Conversation.id == conv_id))
            await session.commit()

        if context.user_data.get('active_conversation_id') == conv_id:
            context.user_data.pop('active_conversation_id', None)

        await query.edit_message_text("✅ Диалог удалён.")
        await asyncio.sleep(2)
        await show_conversations_list(query, user)
    except Exception as e:
        logger.error("Ошибка удаления диалога: %s", e)
        await query.edit_message_text(
            f"❌ Ошибка при удалении: {e}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К списку", callback_data="back_to_list")
            ]]),
        )


# ───────────────────────── Settings ─────────────────────────

async def _show_settings(query, user):
    """Показываем РЕАЛЬНЫЕ настройки юзера из БД."""
    db_user = await get_or_create_user(
        telegram_id=user.id, telegram_username=user.username,
        first_name=user.first_name, last_name=user.last_name,
    )

    async with async_session() as session:
        stmt = select(Setting).where(Setting.user_id == db_user.id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()

    if s is None:
        # На всякий случай — обычно создаётся в get_or_create_user, но на старых юзерах могло быть пусто.
        text = (
            "⚙️ <b>Настройки</b>\n\n"
            "Настроек пока нет. Они будут созданы автоматически при следующем сообщении."
        )
    else:
        notif = "включены" if s.notifications_enabled else "выключены"
        text = (
            "⚙️ <b>Настройки</b>\n\n"
            f"🌡 Temperature: <b>{s.temperature}</b>  <i>(точность ↔ креатив)</i>\n"
            f"🎯 Top P: <b>{s.top_p}</b>  <i>(разнообразие словаря)</i>\n"
            f"📊 Max Tokens: <b>{s.max_tokens}</b>  <i>(лимит длины ответа)</i>\n"
            f"🔔 Уведомления: <b>{notif}</b>\n\n"
            "Меняй значения в веб-интерфейсе на <code>saiga.vaibkod.ru/settings</code>.\n"
            "<i>(In-bot редактирование — следующий этап.)</i>"
        )

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=SettingsKeyboard.get_keyboard())


async def _show_help(query):
    text = (
        "🤖 <b>Saiga AI — Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/new — новый диалог\n"
        "/list — мои диалоги\n"
        "/settings — настройки\n"
        "/help — эта справка\n\n"
        "<b>Что умею:</b>\n"
        "• Отвечать на текстовые сообщения\n"
        "• Голосовые сообщения (распознавание)\n"
        "• Анализ документов (PDF, DOCX)\n\n"
        "Веб-версия: <code>saiga.vaibkod.ru</code> — все диалоги общие."
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=MainMenuKeyboard.get_keyboard())


callback_handler = CallbackQueryHandler(button_callback)
