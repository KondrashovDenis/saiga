import logging
from telegram import Update, Message
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters, ContextTypes
from keyboards.main_menu import MainMenuKeyboard
from models.database import async_session, get_or_create_user
from saiga_shared.models import Setting
from sqlalchemy import select
from utils.conversation_manager import ConversationManager
from utils.llm_client import LLMClient
from utils.markdown_tg import markdown_to_telegram_html, split_for_telegram

logger = logging.getLogger(__name__)


async def _send_formatted(message: Message, text: str, reply_markup=None) -> None:
    chunks = split_for_telegram(markdown_to_telegram_html(text))
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.HTML, reply_markup=markup,
                                     disable_web_page_preview=True)
        except BadRequest as e:
            logger.warning("HTML parse failed, fallback to plain: %s", e)
            plain_chunks = split_for_telegram(text)
            plain = plain_chunks[i] if i < len(plain_chunks) else chunk
            await message.reply_text(plain, reply_markup=markup,
                                     disable_web_page_preview=True)


async def _get_user_settings(user_id: int) -> dict:
    async with async_session() as session:
        stmt = select(Setting).where(Setting.user_id == user_id)
        result = await session.execute(stmt)
        s = result.scalar_one_or_none()
        if s is None:
            return {}
        return {
            "temperature": s.temperature,
            "top_p": s.top_p,
            "max_tokens": s.max_tokens,
        }


async def process_user_message(message: Message, context: ContextTypes.DEFAULT_TYPE,
                               tg_user, text: str, telegram_message_id: int | None = None) -> None:
    """Общий путь: сохранить user-сообщение, спросить LLM, ответить.

    Вызывается из text_handler (юзер написал текст) и из callbacks (юзер нажал
    quick-reply кнопку — мы используем её label как текст).
    """
    logger.info("Сообщение от %s: %s", tg_user.first_name, text[:80])

    try:
        await message.chat.send_action(action="typing")

        db_user = await get_or_create_user(
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code or 'ru'
        )

        conversation_id = context.user_data.get('active_conversation_id') if context.user_data else None

        if conversation_id:
            conversations = await ConversationManager.get_user_conversations(db_user.id)
            conversation = next((c for c in conversations if c.id == conversation_id), None)
            if not conversation:
                conversation = await ConversationManager.create_new_conversation(db_user.id)
                context.user_data['active_conversation_id'] = conversation.id
        else:
            conversation = await ConversationManager.create_new_conversation(db_user.id)
            context.user_data['active_conversation_id'] = conversation.id

        # add_message сам делает auto-rename при первом user-сообщении
        # ("Новый диалог" → first content[:50])
        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=text,
            telegram_message_id=telegram_message_id,
        )

        messages = await ConversationManager.get_conversation_messages(conversation.id)

        llm_messages = [{
            "role": "system",
            "content": "Ты — Saiga, русскоязычный AI-ассистент. Отвечай дружелюбно, информативно и по существу.",
        }]
        for msg in messages:
            llm_messages.append({"role": msg.role, "content": msg.content})

        user_settings = await _get_user_settings(db_user.id)
        ai_response = await LLMClient.generate_response(llm_messages, **user_settings)

        await ConversationManager.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,
        )

        await _send_formatted(message, ai_response, reply_markup=MainMenuKeyboard.get_quick_replies())

    except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", e, exc_info=True)
        await message.reply_text("😔 Извините, произошла ошибка. Попробуйте ещё раз.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_user_message(
        message=update.message,
        context=context,
        tg_user=update.effective_user,
        text=update.message.text,
        telegram_message_id=update.message.message_id,
    )


text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
