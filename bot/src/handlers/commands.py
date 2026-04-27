from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes
from keyboards.main_menu import MainMenuKeyboard
from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Saiga AI - Справка**

**Основные команды:**
/start - Начать работу
/new - Создать новый диалог
/list - Показать мои диалоги  
/settings - Настройки
/help - Эта справка

**Как пользоваться:**
- Просто напишите сообщение для общения с AI
- Используйте кнопки быстрых ответов
- Отправляйте голосовые сообщения
- Прикрепляйте документы для анализа

**Дополнительно:**
- Поддержка Markdown форматирования
- Настройка параметров генерации
- Сохранение истории диалогов
- Синхронизация с веб-версией

❓ Есть вопросы? Просто спросите меня!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    db_user = await get_or_create_user(
        telegram_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    conversation = await ConversationManager.create_new_conversation(db_user.id)
    
    # Сохраняем ID активного диалога в контексте
    context.user_data['active_conversation_id'] = conversation.id
    
    await update.message.reply_text(
        f"💬 Создан новый диалог!\n\n🆔 Диалог #{conversation.id}\n📝 Теперь можете задать свой вопрос!",
        reply_markup=MainMenuKeyboard.get_quick_replies()
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    db_user = await get_or_create_user(
        telegram_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    conversations = await ConversationManager.get_user_conversations(db_user.id)
    
    if not conversations:
        text = "📋 У вас пока нет диалогов.\n\nИспользуйте /new чтобы создать первый диалог!"
        await update.message.reply_text(text)
        return
    
    # Создаем интерактивный список диалогов
    text = "📋 **Ваши диалоги:**\n\nВыберите диалог для продолжения:\n\n"
    keyboard = []
    
    for conv in conversations:
        message_count = len(conv.messages) if conv.messages else 0
        title = conv.title if conv.title and conv.title != "Новый диалог" else f"Диалог #{conv.id}"
        
        # Кнопка для выбора диалога
        button_text = f"💬 {title} ({message_count} сообщений)"
        callback_data = f"select_conv_{conv.id}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Добавляем кнопку создания нового диалога
    keyboard.append([InlineKeyboardButton("➕ Новый диалог", callback_data="new_conversation")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards.settings import SettingsKeyboard
    
    settings_text = """
⚙️ **Настройки**

**Текущие параметры:**
- Temperature: 0.7
- Top P: 0.9
- Max Tokens: 2048
- Язык: Русский

Используйте кнопки ниже для изменения настроек:
    """
    
    await update.message.reply_text(
        settings_text,
        parse_mode='Markdown',
        reply_markup=SettingsKeyboard.get_keyboard()
    )

command_handlers = [
    CommandHandler('help', help_command),
    CommandHandler('new', new_command),
    CommandHandler('list', list_command),
    CommandHandler('settings', settings_command)
]
