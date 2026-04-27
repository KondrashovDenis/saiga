import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters, ContextTypes
from keyboards.main_menu import MainMenuKeyboard
from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager
from utils.llm_client import LLMClient
from utils.markdown_tg import markdown_to_telegram_html, split_for_telegram

logger = logging.getLogger(__name__)


async def _send_formatted(message, text: str, reply_markup=None) -> None:
    """Отправить ответ LLM с рендером markdown → Telegram HTML.

    Telegram HTML может фейлиться если LLM выдаст невалидный markup
    (несбалансированные звёздочки и т.д.). В таких случаях fallback
    к plain text без parse_mode — пользователь хотя бы текст увидит.
    """
    chunks = split_for_telegram(markdown_to_telegram_html(text))
    for i, chunk in enumerate(chunks):
        # Кнопки прикрепляем только к последнему чанку
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.HTML, reply_markup=markup,
                                     disable_web_page_preview=True)
        except BadRequest as e:
            logger.warning("HTML parse failed, fallback to plain: %s", e)
            # Fallback — берём оригинальный кусок (соответствующий по позиции)
            plain_chunks = split_for_telegram(text)
            plain = plain_chunks[i] if i < len(plain_chunks) else chunk
            await message.reply_text(plain, reply_markup=markup,
                                     disable_web_page_preview=True)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text

    logger.info("Сообщение от %s: %s", user.first_name, message_text)

    try:
        await update.message.chat.send_action(action="typing")

        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code or 'ru'
        )

        conversation_id = context.user_data.get('active_conversation_id')

        if conversation_id:
            conversations = await ConversationManager.get_user_conversations(db_user.id)
            conversation = next((c for c in conversations if c.id == conversation_id), None)
            if not conversation:
                conversation = await ConversationManager.create_new_conversation(db_user.id)
                context.user_data['active_conversation_id'] = conversation.id
        else:
            conversation = await ConversationManager.create_new_conversation(db_user.id)
            context.user_data['active_conversation_id'] = conversation.id

        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=message_text,
            telegram_message_id=update.message.message_id,
        )

        messages = await ConversationManager.get_conversation_messages(conversation.id)

        llm_messages = [{
            "role": "system",
            "content": "Ты — Saiga, русскоязычный AI-ассистент. Отвечай дружелюбно, информативно и по существу.",
        }]
        for msg in messages:
            llm_messages.append({"role": msg.role, "content": msg.content})

        ai_response = await LLMClient.generate_response(llm_messages)

        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,  # храним сырой markdown — web сам отрендерит
        )

        await _send_formatted(
            update.message,
            ai_response,
            reply_markup=MainMenuKeyboard.get_quick_replies(),
        )

    except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", e, exc_info=True)
        await update.message.reply_text("😔 Извините, произошла ошибка. Попробуйте ещё раз.")


text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
