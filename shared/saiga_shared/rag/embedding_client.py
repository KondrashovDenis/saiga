"""HTTP-клиент к saiga-embedding сервису.

Sync-only (через requests). Если из bot async-кода нужен embedding —
оборачивай вызовы в asyncio.to_thread / loop.run_in_executor.

requests умышленно не подтянут как обязательная зависимость shared/setup.py:
- web уже имеет requests в requirements.txt;
- bot имеет httpx — но клиент embedding в bot не нужен на этапе 1;
- если кто-то импортит EmbeddingClient без requests — упадёт на ImportError
  с понятным сообщением (в тестах bot этот модуль не дёргают).
"""
from __future__ import annotations

from typing import Literal


class EmbeddingClient:
    """Тонкий sync клиент.

    Args:
        base_url: например http://saiga-embedding:8000 (внутри docker) или
            https://embedding.vaibkod.ru (если решим выставить через Caddy).
        api_key: Bearer-токен — должен совпадать с EMBEDDING_API_KEY у сервиса.
        timeout: общий таймаут запроса в секундах. Encode на CPU для одной
            строки занимает 100-300ms, для batch=64 — 5-10s. Дефолт 30.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def embed(self, text: str, kind: Literal["passage", "query"] = "passage") -> list[float]:
        """Embed одной строки. Возвращает 1024-мерный вектор."""
        import requests
        r = requests.post(
            f"{self.base_url}/embed",
            json={"text": text, "kind": kind},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["vector"]

    def embed_batch(
        self,
        texts: list[str],
        kind: Literal["passage", "query"] = "passage",
    ) -> list[list[float]]:
        """Embed списка строк (max 64 за раз — лимит сервиса).

        Если текстов больше — режь сам в вызывающем коде. Не делаем авто-чанкинг
        тут, чтобы не прятать выбор размера batch от вызывающего.
        """
        if len(texts) > 64:
            raise ValueError(f"embed_batch принимает max 64 текста, передано {len(texts)}")
        import requests
        r = requests.post(
            f"{self.base_url}/embed/batch",
            json={"texts": texts, "kind": kind},
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["vectors"]

    def healthz(self) -> dict:
        import requests
        r = requests.get(f"{self.base_url}/healthz", timeout=5.0)
        r.raise_for_status()
        return r.json()
