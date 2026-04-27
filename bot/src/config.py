import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    BOT_USERNAME = '@saiga_ai_bot'
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:////app/data/saiga_bot.db')
    
    # LLM API  
    LLM_API_URL = os.getenv('LLM_API_URL', 'http://saiga-llm:5000/v1/chat/completions')
    
    # Default settings
    DEFAULT_TEMPERATURE = float(os.getenv('DEFAULT_TEMPERATURE', '0.7'))
    DEFAULT_TOP_P = float(os.getenv('DEFAULT_TOP_P', '0.9'))
    DEFAULT_MAX_TOKENS = int(os.getenv('DEFAULT_MAX_TOKENS', '2048'))
    
    # Admin
    ADMIN_TELEGRAM_IDS = [
        int(x.strip()) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') 
        if x.strip().isdigit()
    ]
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://saiga-bot-redis:6379/0')
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = '/app/data'
    LOGS_DIR = '/app/logs'
