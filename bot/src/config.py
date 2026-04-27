import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Environment variable {name} is required but not set. "
            f"Define it in bot/.env (see bot/.env.example)."
        )
    return val


class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = _required('TELEGRAM_BOT_TOKEN')
    BOT_USERNAME = '@saiga_ai_bot'

    # Database — обязателен (никаких dev-fallback)
    DATABASE_URL = _required('DATABASE_URL')

    # LLM API — снаружи через домен с Bearer-токеном
    LLM_API_URL = os.getenv('LLM_API_URL', 'https://llm.vaibkod.ru/v1/chat/completions')
    LLM_API_KEY = os.getenv('LLM_API_KEY')  # Опционально: если задан — добавляется Authorization: Bearer ...

    # Default generation settings
    DEFAULT_TEMPERATURE = float(os.getenv('DEFAULT_TEMPERATURE', '0.7'))
    DEFAULT_TOP_P = float(os.getenv('DEFAULT_TOP_P', '0.9'))
    DEFAULT_MAX_TOKENS = int(os.getenv('DEFAULT_MAX_TOKENS', '2048'))

    # Admins
    ADMIN_TELEGRAM_IDS = [
        int(x.strip()) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',')
        if x.strip().isdigit()
    ]

    # Redis (локальный sidecar в docker compose)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://saiga-bot-redis:6379/0')

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = '/app/data'
    LOGS_DIR = '/app/logs'
