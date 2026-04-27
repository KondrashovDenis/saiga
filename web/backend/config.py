import os
from datetime import timedelta

class Config:
    # Базовая директория проекта
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Секретный ключ для подписи сессий и т.д.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Настройки SQLite БД
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 
                                           f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки для Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    # Настройки для LLM API
    LLM_API_URL = os.environ.get('LLM_API_URL', 'http://localhost:7860/api/v1/generate')
    LLM_DEFAULT_TEMPERATURE = 0.7
    LLM_DEFAULT_TOP_P = 0.9
    LLM_DEFAULT_MAX_TOKENS = 2048
    
    # Telegram Bot настройки
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', 'saiga_ai_bot')
    
    # Параметры приложения
    MAX_CONVERSATIONS_PER_USER = 50  # Максимальное число диалогов на пользователя
    MAX_MESSAGES_PER_CONVERSATION = 100  # Максимальное число сообщений в диалоге
