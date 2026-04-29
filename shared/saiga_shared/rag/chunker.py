"""Простой text chunker для RAG.

Подход: разбиваем по абзацам (двойной \\n) → если абзац длиннее лимита, режем
по предложениям → если предложение длиннее, режем по словам. Сохраняем семантику
насколько возможно, ловим overlap чтобы соседние chunks делили контекст.

Размер мерим в "приближённых токенах" через простой эвристик: 1 токен ≈ 4 символа
для смеси кириллицы и латиницы. Это завышает в 1.3-1.5 раза от честного BPE, что
нам наруку — лучше короче chunks чем длиннее.

НЕ зависит от tiktoken / transformers — должен работать и в тестовых
окружениях bot где этих пакетов нет.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator


_PARAGRAPH_RE = re.compile(r"\n\s*\n")
# Грубая нарезка по предложениям: точка/восклицание/вопрос + пробел или конец.
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class ChunkerConfig:
    """Параметры chunking.

    target_tokens — целевой размер chunk'а в "псевдо-токенах" (1 токен ≈ 4 символа).
    overlap_tokens — сколько токенов из конца предыдущего chunk'а копируется
        в начало следующего (повышает recall на запросах, попадающих на стык).
    min_chunk_tokens — chunk короче этого склеивается со следующим (не плодим
        embedding'ов на 5-словные обрывки).
    """
    target_tokens: int = 500
    overlap_tokens: int = 50
    min_chunk_tokens: int = 80


_CHARS_PER_TOKEN = 4


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _split_long_paragraph(para: str, max_chars: int) -> list[str]:
    """Если абзац длиннее max_chars — режем по предложениям, потом по словам.

    Возвращает части, каждая из которых короче max_chars (по символам).
    """
    if len(para) <= max_chars:
        return [para]

    parts: list[str] = []
    sentences = _SENTENCE_RE.split(para) or [para]
    for sent in sentences:
        if len(sent) <= max_chars:
            parts.append(sent)
            continue
        # Слишком длинное предложение — режем по словам.
        words = sent.split()
        cur = ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_chars:
                parts.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, config: ChunkerConfig | None = None) -> list[dict]:
    """Разбить text на список chunks.

    Возвращает [{"index": int, "text": str, "token_count": int}, ...]
    Индекс — порядковый номер chunk'а в документе (0-based).

    Алгоритм:
    1. Нормализуем переносы (\\r\\n → \\n).
    2. Делим на абзацы.
    3. Жадно набираем абзацы в текущий chunk пока < target_tokens.
    4. Если один абзац длиннее target_tokens — режем его в _split_long_paragraph.
    5. Между chunks применяем overlap (последние overlap_tokens из предыдущего).
    """
    if not text or not text.strip():
        return []

    config = config or ChunkerConfig()
    max_chars = config.target_tokens * _CHARS_PER_TOKEN
    overlap_chars = config.overlap_tokens * _CHARS_PER_TOKEN
    min_chars = config.min_chunk_tokens * _CHARS_PER_TOKEN

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]

    # Раскрываем длинные абзацы на под-абзацы — после этого все элементы
    # короче max_chars.
    units: list[str] = []
    for p in paragraphs:
        units.extend(_split_long_paragraph(p, max_chars))

    # Жадно набираем chunk до max_chars.
    raw_chunks: list[str] = []
    cur = ""
    for unit in units:
        if not cur:
            cur = unit
            continue
        if len(cur) + 2 + len(unit) <= max_chars:
            cur = f"{cur}\n\n{unit}"
        else:
            raw_chunks.append(cur)
            cur = unit
    if cur:
        raw_chunks.append(cur)

    # Склеить слишком короткие хвосты с предыдущими.
    merged: list[str] = []
    for c in raw_chunks:
        if merged and len(c) < min_chars and len(merged[-1]) + 2 + len(c) <= max_chars * 2:
            merged[-1] = f"{merged[-1]}\n\n{c}"
        else:
            merged.append(c)

    # Применяем overlap: к каждому chunk кроме первого префиксируем
    # последние overlap_chars из предыдущего raw chunk'а.
    final: list[dict] = []
    prev_tail = ""
    for i, c in enumerate(merged):
        body = f"{prev_tail}\n\n{c}".strip() if prev_tail else c
        final.append({
            "index": i,
            "text": body,
            "token_count": _approx_tokens(body),
        })
        prev_tail = c[-overlap_chars:] if overlap_chars > 0 else ""

    return final


def iter_chunks(text: str, config: ChunkerConfig | None = None) -> Iterator[dict]:
    """Yield версия chunk_text — для случаев когда не хочется держать всё в памяти."""
    yield from chunk_text(text, config)
