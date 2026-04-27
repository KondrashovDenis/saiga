import os
import tempfile
import logging
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes

from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager
from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов в Telegram"""
    user = update.effective_user
    document = update.message.document
    
    logger.info(f"Получен документ от {user.first_name}: {document.file_name}")
    
    try:
        # Отправляем уведомление о начале обработки
        await update.message.reply_text("📄 Обрабатываю документ...")
        
        # Получаем или создаем пользователя
        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Получаем активный диалог
        conversation_id = context.user_data.get('active_conversation_id')
        if not conversation_id:
            conversation = await ConversationManager.create_new_conversation(db_user.id)
            context.user_data['active_conversation_id'] = conversation.id
            conversation_id = conversation.id
        
        # Проверяем размер файла (максимум 10MB)
        if document.file_size > 10 * 1024 * 1024:
            await update.message.reply_text("❌ Файл слишком большой (максимум 10MB)")
            return
        
        # Проверяем тип файла
        allowed_extensions = ['.txt', '.pdf', '.docx', '.md']
        file_ext = os.path.splitext(document.file_name)[1].lower()
        
        if file_ext not in allowed_extensions:
            await update.message.reply_text(
                f"❌ Неподдерживаемый тип файла: {file_ext}\n"
                f"Поддерживаются: {', '.join(allowed_extensions)}"
            )
            return
        
        # Скачиваем файл
        file = await context.bot.get_file(document.file_id)
        
        # Сохраняем во временную директорию
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_path = temp_file.name
                await file.download_to_drive(temp_path)
            
            # Обрабатываем документ
            from utils.document_processor import DocumentProcessor
            extracted_text, file_type = DocumentProcessor.process_document(temp_path)
            
            # Формируем сообщение
            content = f"📄 Файл: {document.file_name}\n\n{extracted_text}"
            
            # Сохраняем сообщение пользователя
            await ConversationManager.add_message(
                conversation_id=conversation_id,
                role="user",
                content=content,
                telegram_message_id=update.message.message_id
            )
            
            # Уведомляем о успешной обработке
            await update.message.reply_text(
                f"✅ Документ обработан!\n"
                f"📊 Извлечено текста: {len(extracted_text)} символов\n"
                f"💬 Теперь можете задать вопрос по содержимому документа"
            )
            
        finally:
            # Удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(
            "❌ Ошибка при обработке документа. Попробуйте еще раз."
        )

# Создаем обработчик для документов
document_handler = MessageHandler(filters.Document.ALL, handle_document)
