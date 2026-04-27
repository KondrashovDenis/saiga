import logging
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from keyboards.main_menu import MainMenuKeyboard
from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager
from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"Сообщение от {user.first_name}: {message_text}")
    
    try:
        await update.message.chat.send_action(action="typing")
        
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code or 'ru'
        )
        
        # Проверяем, есть ли выбранный диалог в контексте
        conversation_id = context.user_data.get('active_conversation_id')
        
        if conversation_id:
            # Используем выбранный диалог
            conversations = await ConversationManager.get_user_conversations(db_user.id)
            conversation = None
            for conv in conversations:
                if conv.id == conversation_id:
                    conversation = conv
                    break
            
            if not conversation:
                # Диалог не найден, создаем новый
                conversation = await ConversationManager.create_new_conversation(db_user.id)
                context.user_data['active_conversation_id'] = conversation.id
        else:
            # Нет выбранного диалога, создаем новый
            conversation = await ConversationManager.create_new_conversation(db_user.id)
            context.user_data['active_conversation_id'] = conversation.id
        
        # Добавляем сообщение пользователя
        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=message_text,
            telegram_message_id=update.message.message_id
        )
        
        # Получаем историю сообщений
        messages = await ConversationManager.get_conversation_messages(conversation.id)
        
        # Формируем контекст для LLM
        llm_messages = []
        system_prompt = {
            "role": "system",
            "content": "Ты - Saiga, русскоязычный AI-ассистент. Отвечай дружелюбно, информативно и по существу."
        }
        llm_messages.append(system_prompt)
        
        for msg in messages:
            llm_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Получаем ответ от LLM
        ai_response = await LLMClient.generate_response(llm_messages)
        
        # Сохраняем ответ ассистента
        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="assistant", 
            content=ai_response
        )
        
        # Отправляем ответ пользователю
        await update.message.reply_text(
            ai_response,
            reply_markup=MainMenuKeyboard.get_quick_replies()
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text(
            "😔 Извините, произошла ошибка. Попробуйте еще раз."
        )

text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
