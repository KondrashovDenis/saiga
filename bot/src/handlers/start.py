import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import async_session
from models.user import User
from models.setting import Setting
from keyboards.main_menu import MainMenuKeyboard

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    async with async_session() as session:
        # Проверяем, есть ли пользователь в базе
        stmt = select(User).where(User.telegram_id == user.id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            # Создаем нового пользователя
            db_user = User(
                telegram_id=user.id,
                telegram_username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code or 'ru'
            )
            session.add(db_user)
            await session.commit()
            
            # Создаем настройки по умолчанию
            settings = Setting(user_id=db_user.id)
            session.add(settings)
            await session.commit()
            
            logger.info(f"Новый пользователь: {user.full_name} (@{user.username})")
            
            welcome_text = f"""
🤖 Добро пожаловать в Saiga AI, {user.first_name}!

Я - ваш персональный AI-ассистент на основе языковой модели Saiga Nemo 12B.

🔥 **Мои возможности:**
• 💬 Ведение диалогов на любые темы
• 📚 Помощь с учебой и работой  
• 🧠 Решение задач и объяснения
• 📄 Анализ документов
• 🎤 Обработка голосовых сообщений

📋 **Основные команды:**
/new - Начать новый диалог
/list - Мои диалоги
/settings - Настройки
/help - Помощь

Просто напишите мне сообщение, и мы начнем общаться! 🚀
            """
        else:
            welcome_text = f"""
👋 С возвращением, {user.first_name}!

Готов продолжить наше общение. Что вас интересует?
            """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=MainMenuKeyboard.get_keyboard()
    )

# Создаем обработчик
start_handler = CommandHandler('start', start_command)
