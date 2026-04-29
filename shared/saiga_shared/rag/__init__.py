"""RAG-инфраструктура: chunking входящих документов + retrieval по embedding.

Модули:
- chunker: разбить текст на куски ~N токенов с overlap.
- embedding_client: тонкий HTTP клиент к saiga-embedding (sync) — нужен
  и web (sync routes) и bot (async — обернёт в asyncio.to_thread при нужде).
- retrieval: SA-helper "embed query → cosine search top-K в chunks".

Импорты намеренно lazy внутри файлов — чтобы импорт saiga_shared.rag не
тянул requests / numpy если их не используют.
"""

from saiga_shared.rag.chunker import chunk_text, ChunkerConfig
from saiga_shared.rag.embedding_client import EmbeddingClient

__all__ = [
    "chunk_text",
    "ChunkerConfig",
    "EmbeddingClient",
]
