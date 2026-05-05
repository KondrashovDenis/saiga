#!/usr/bin/env python3
import logging
import os
from datetime import datetime

from telegram.ext import Application

from config import Config

# ────────────── Sentry ──────────────
# Инициализируем как можно раньше — чтобы поймать ошибки даже на startup.
# Если SENTRY_DSN не задан, init не падает, просто всё no-op.
if Config.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=Config.SENTRY_DSN,
        environment=Config.SENTRY_ENV,
        release=Config.SENTRY_RELEASE,
        traces_sample_rate=0.1,       # 10% запросов в performance trace
        send_default_pii=False,       # не шлём username/email юзеров без явного запроса
    )

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
    from handlers.settings_edit import (
        settings_conversation_handler,
        toggle_notifications_handler,
    )
    from handlers.name_setup import name_setup_handler
    from handlers.new_conversation import new_conversation_handler
    from handlers.web_login import web_command_handler, web_callback_handler
    from handlers.text_handler import text_handler
    from handlers.document_handler import document_handler

    application.add_handler(start_handler)

    # Settings ConversationHandler и toggle регистрируем ДО callback_handler,
    # чтобы они перехватывали свои callback-паттерны раньше общего роутера.
    application.add_handler(settings_conversation_handler)
    application.add_handler(toggle_notifications_handler)
    application.add_handler(name_setup_handler)
    application.add_handler(new_conversation_handler)
    application.add_handler(web_command_handler)
    application.add_handler(web_callback_handler)

    application.add_handler(callback_handler)
    application.add_handler(document_handler)

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
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        # exc_info=True важно — Sentry вытягивает traceback из текущего sys.exc_info()
        raise  # перебросим, чтобы Sentry зарегистрировал и контейнер restart'нулся
