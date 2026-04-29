# Реэкспорт shared-моделей. Чтобы старые импорты `from models.user import User`
# в web/backend/routes/* продолжали работать без правок.
from saiga_shared.models import (
    Base,
    User,
    Conversation,
    Message,
    Setting,
    TelegramLinkToken,
    KnowledgeBase,
    Document,
    Chunk,
)

__all__ = [
    "Base",
    "User",
    "Conversation",
    "Message",
    "Setting",
    "TelegramLinkToken",
    "KnowledgeBase",
    "Document",
    "Chunk",
]
