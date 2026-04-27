from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
from keyboards.main_menu import MainMenuKeyboard
from keyboards.settings import SettingsKeyboard
from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий inline-кнопок"""
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие
    
    data = query.data
    user = update.effective_user
    
    if data == "new_conversation":
        # Создаем новый диалог
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        conversation = await ConversationManager.create_new_conversation(db_user.id)
        context.user_data['active_conversation_id'] = conversation.id
        
        await query.edit_message_text(
            f"💬 Создан новый диалог #{conversation.id}!\n\nТеперь можете задать свой вопрос!",
            reply_markup=MainMenuKeyboard.get_quick_replies()
        )
    
    elif data.startswith("select_conv_"):
        # Выбираем существующий диалог
        conv_id = int(data.replace("select_conv_", ""))
        context.user_data['active_conversation_id'] = conv_id
        
        # Получаем информацию о диалоге
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Получаем диалог и последние сообщения
        conversations = await ConversationManager.get_user_conversations(db_user.id)
        selected_conv = None
        for conv in conversations:
            if conv.id == conv_id:
                selected_conv = conv
                break
        
        if selected_conv:
            title = selected_conv.title if selected_conv.title and selected_conv.title != "Новый диалог" else f"Диалог #{conv_id}"
            message_count = len(selected_conv.messages) if selected_conv.messages else 0
            
            # Показываем информацию о выбранном диалоге с кнопкой истории
            text = f"📖 **{title}**\n\n"
            text += f"💬 Сообщений: {message_count}\n"
            text += f"📅 Обновлен: {selected_conv.updated_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            text += "Теперь можете продолжить общение в этом диалоге!"
            
            # Создаем специальную клавиатуру с кнопкой истории
            keyboard = [
                [InlineKeyboardButton("📋 Посмотреть содержание диалога", callback_data=f"show_history_{conv_id}")],
                [InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                "❌ Диалог не найден.",
                reply_markup=MainMenuKeyboard.get_keyboard()
            )
    
    elif data.startswith("show_history_"):
        # Показываем историю диалога
        conv_id = int(data.replace("show_history_", ""))
        
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Получаем сообщения диалога
        messages = await ConversationManager.get_conversation_messages(conv_id)
        
        if not messages:
            text = "📭 В этом диалоге пока нет сообщений."
        else:
            # Получаем информацию о диалоге
            conversations = await ConversationManager.get_user_conversations(db_user.id)
            selected_conv = None
            for conv in conversations:
                if conv.id == conv_id:
                    selected_conv = conv
                    break
            
            title = selected_conv.title if selected_conv and selected_conv.title and selected_conv.title != "Новый диалог" else f"Диалог #{conv_id}"
            
            text = f"📋 **История диалога: {title}**\n\n"
            
            # Добавляем последние 10 сообщений (чтобы не превысить лимит Telegram)
            recent_messages = messages[-10:] if len(messages) > 10 else messages
            
            if len(messages) > 10:
                text += f"_(Показаны последние 10 из {len(messages)} сообщений)_\n\n"
            
            for i, msg in enumerate(recent_messages, 1):
                if msg.role == 'user':
                    text += f"👤 **Вы:** {msg.content}\n\n"
                else:
                    # Ограничиваем длину ответа ассистента
                    content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                    text += f"🤖 **Saiga:** {content}\n\n"
                
                # Telegram имеет лимит на длину сообщения
                if len(text) > 3500:
                    text += "_...история обрезана из-за ограничений Telegram_"
                    break
        
        # Кнопки для возврата и удаления
        keyboard = [
            [InlineKeyboardButton("🔙 Назад к диалогу", callback_data=f"select_conv_{conv_id}")],
            [InlineKeyboardButton("🗑 Удалить этот диалог", callback_data=f"confirm_delete_{conv_id}")],
            [InlineKeyboardButton("📋 К списку диалогов", callback_data="back_to_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data.startswith("confirm_delete_"):
        # Подтверждение удаления диалога
        conv_id = int(data.replace("confirm_delete_", ""))
        
        # Получаем информацию о диалоге для отображения
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        conversations = await ConversationManager.get_user_conversations(db_user.id)
        selected_conv = None
        for conv in conversations:
            if conv.id == conv_id:
                selected_conv = conv
                break
        
        if selected_conv:
            title = selected_conv.title if selected_conv.title and selected_conv.title != "Новый диалог" else f"Диалог #{conv_id}"
            message_count = len(selected_conv.messages) if selected_conv.messages else 0
            
            text = "⚠️ **Подтверждение удаления**\n\n"
            text += "Вы действительно хотите удалить диалог?\n\n"
            text += f"📖 **{title}**\n"
            text += f"💬 Сообщений: {message_count}\n\n"
            text += "⚠️ **Это действие нельзя отменить!**"
            
            # Кнопки подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirmed_{conv_id}"),
                    InlineKeyboardButton("❌ Отмена", callback_data=f"show_history_{conv_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                "❌ Диалог не найден.",
                reply_markup=MainMenuKeyboard.get_keyboard()
            )
    
    elif data.startswith("delete_confirmed_"):
        # Выполняем удаление диалога
        conv_id = int(data.replace("delete_confirmed_", ""))
        
        try:
            # Удаляем диалог через ConversationManager
            from models.database import async_session
            from models.conversation import Conversation
            from models.message import Message
            from sqlalchemy import delete
            
            async with async_session() as session:
                # Удаляем все сообщения диалога
                await session.execute(delete(Message).where(Message.conversation_id == conv_id))
                
                # Удаляем сам диалог
                await session.execute(delete(Conversation).where(Conversation.id == conv_id))
                
                await session.commit()
            
            # Очищаем активный диалог из контекста, если он был удален
            if context.user_data.get('active_conversation_id') == conv_id:
                context.user_data.pop('active_conversation_id', None)
            
            await query.edit_message_text(
                "✅ **Диалог успешно удален!**\n\nВсе сообщения и история диалога были удалены без возможности восстановления.",
                parse_mode='Markdown'
            )
            
            # Через 3 секунды показываем список диалогов
            import asyncio
            await asyncio.sleep(3)
            
            # Переходим к списку диалогов
            await show_conversations_list(query, user)
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ **Ошибка при удалении диалога**\n\nПопробуйте еще раз или обратитесь к администратору.\n\n_Ошибка: {str(e)}_",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 К списку диалогов", callback_data="back_to_list")
                ]])
            )
    
    elif data == "back_to_list":
        # Возврат к списку диалогов
        await show_conversations_list(query, user)
    
    # Остальные обработчики остаются без изменений...
    elif data == "list_conversations":
        await query.edit_message_text(
            "📋 **Мои диалоги:**\n\n• Диалог 1: Помощь с Python\n• Диалог 2: Объяснение квантовой физики\n• Диалог 3: Рецепты борща\n\n_Полный функционал диалогов будет добавлен в следующей версии._",
            parse_mode='Markdown',
            reply_markup=MainMenuKeyboard.get_keyboard()
        )
    
    elif data == "settings":
        settings_text = """
⚙️ **Настройки**

**Текущие параметры:**
- Temperature: 0.7
- Top P: 0.9  
- Max Tokens: 2048
- Язык: Русский

Используйте кнопки ниже для изменения настроек:
        """
        await query.edit_message_text(
            settings_text,
            parse_mode='Markdown',
            reply_markup=SettingsKeyboard.get_keyboard()
        )
    
    elif data == "help":
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

❓ Есть вопросы? Просто спросите меня!
        """
        await query.edit_message_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=MainMenuKeyboard.get_keyboard()
        )
    
    elif data == "main_menu":
        await query.edit_message_text(
            "🤖 Главное меню\n\nВыберите нужное действие:",
            reply_markup=MainMenuKeyboard.get_keyboard()
        )
    
    elif data.startswith("quick_"):
        quick_replies = {
            "quick_continue": "Продолжи",
            "quick_explain": "Поясни подробнее", 
            "quick_example": "Дай пример",
            "quick_what": "Что это значит?"
        }
        
        text = quick_replies.get(data, "Неизвестная команда")
        await query.edit_message_text(
            f"Вы выбрали: **{text}**\n\n_Функция в разработке. Скоро будет интеграция с LLM!_",
            parse_mode='Markdown',
            reply_markup=MainMenuKeyboard.get_keyboard()
        )
    
    else:
        await query.edit_message_text(
            f"Настройка **{data}** в разработке!\n\n_Скоро будет доступна._",
            parse_mode='Markdown',
            reply_markup=SettingsKeyboard.get_keyboard()
        )

async def show_conversations_list(query, user):
    """Вспомогательная функция для показа списка диалогов"""
    db_user = await get_or_create_user(
        telegram_id=user.id,
        telegram_username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    conversations = await ConversationManager.get_user_conversations(db_user.id)
    
    if not conversations:
        text = "📋 У вас пока нет диалогов.\n\nИспользуйте /new чтобы создать первый диалог!"
        await query.edit_message_text(text)
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
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Создаем обработчик
callback_handler = CallbackQueryHandler(button_callback)
