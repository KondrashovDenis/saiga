#!/usr/bin/env python3
import logging
import os
from datetime import datetime

from telegram.ext import Application

from config import Config

os.makedirs(Config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{Config.LOGS_DIR}/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_handlers_sync(application):
    from handlers.start import start_handler
    from handlers.commands import command_handlers
    from handlers.callbacks import callback_handler
    from handlers.text_handler import text_handler
    from handlers.document_handler import document_handler  # НОВЫЙ ОБРАБОТЧИК
    
    application.add_handler(start_handler)
    application.add_handler(callback_handler)
    application.add_handler(document_handler)  # ДОБАВЛЯЕМ ОБРАБОТЧИК ДОКУМЕНТОВ
    
    for handler in command_handlers:
        application.add_handler(handler)
    
    application.add_handler(text_handler)
    
    logger.info("✅ Обработчики настроены (включая документы)")

def main():
    logger.info("🚀 Запуск Saiga Telegram Bot...")
    
    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    logger.info("🤖 Создание Telegram приложения...")
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    logger.info("⚙️ Настройка обработчиков...")
    setup_handlers_sync(application)
    
    logger.info(f"✅ Saiga Bot {Config.BOT_USERNAME} запущен!")
    logger.info(f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота по команде пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
