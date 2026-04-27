"""Конвертер markdown → Telegram HTML.

Telegram HTML формат поддерживает только узкий набор тэгов:
  <b>, <strong>, <i>, <em>, <u>, <s>, <code>, <pre>, <a href>,
  <blockquote>, <tg-spoiler>.

Заголовки (#, ##, ###) и списки (<ul>, <ol>, <li>) Telegram НЕ умеет,
поэтому конвертируем:
  ### Header → <b>Header</b> + \\n
  - item     → • item
  1. item    → 1. item   (оставляем как plain — Telegram умеет цифры)
"""

from __future__ import annotations
import re
from typing import List

# ───── escape HTML спецсимволов вне форматирования ─────
def _esc(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# inline-форматирование: bold/italic/code/links
# Применяется уже к escaped тексту (без сырых < и >).
def _inline(s: str) -> str:
    # 1) inline code сначала (внутри не парсим)
    parts: List[str] = []

    def take_code(m: 're.Match[str]') -> str:
        parts.append(m.group(1))
        return f'\x00CODE{len(parts) - 1}\x00'

    s = re.sub(r'`([^`\n]+)`', take_code, s)

    # 2) bold **
    s = re.sub(r'\*\*([^*\n]+)\*\*', r'<b>\1</b>', s)
    # 3) italic * (не звёздочки в списках — но списки уже преобразованы)
    s = re.sub(r'(^|[^*])\*([^*\n]+)\*(?!\*)', r'\1<i>\2</i>', s)
    # 4) italic _underscore_
    s = re.sub(r'(^|\W)_([^_\n]+)_(?!\w)', r'\1<i>\2</i>', s)
    # 5) [text](url) — url экранируем
    def link(m: 're.Match[str]') -> str:
        text, url = m.group(1), m.group(2)
        # url уже escaped (мы делали _esc до этого), просто закавычиваем
        return f'<a href="{url}">{text}</a>'
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)

    # 6) восстановить inline code
    def restore(m: 're.Match[str]') -> str:
        idx = int(m.group(1))
        return f'<code>{_esc(parts[idx])}</code>'
    s = re.sub(r'\x00CODE(\d+)\x00', restore, s)
    return s


def markdown_to_telegram_html(text: str) -> str:
    """Главный конвертер. Возвращает строку готовую для parse_mode=HTML."""
    if not text:
        return ''

    # 1) выделить fenced code blocks ```...``` и заменить плейсхолдером
    code_blocks: List[str] = []

    def take_block(m: 're.Match[str]') -> str:
        code = m.group(2).rstrip('\n')
        code_blocks.append(code)
        return f'\x01BLOCK{len(code_blocks) - 1}\x01'

    text = re.sub(r'```(\w+)?\n?([\s\S]*?)```', take_block, text)

    # 2) Escape HTML спецсимволов
    text = _esc(text)

    # 3) Построчный обход
    lines = text.split('\n')
    out_lines: List[str] = []
    for ln in lines:
        stripped = ln.strip()

        # placeholder code-block
        m = re.match(r'^\x01BLOCK(\d+)\x01$', stripped)
        if m:
            idx = int(m.group(1))
            out_lines.append(f'<pre><code>{_esc(code_blocks[idx])}</code></pre>')
            continue

        # heading: # ## ### #### → <b>...</b>
        h = re.match(r'^(#{1,4})\s+(.+?)\s*#*$', stripped)
        if h:
            out_lines.append(f'<b>{_inline(h.group(2))}</b>')
            continue

        # bullet list: -, *, +
        b = re.match(r'^[-*+]\s+(.+)', stripped)
        if b:
            out_lines.append(f'• {_inline(b.group(1))}')
            continue

        # numbered list: 1. 2. ...
        nl = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if nl:
            out_lines.append(f'{nl.group(1)}. {_inline(nl.group(2))}')
            continue

        # обычная строка
        out_lines.append(_inline(ln))

    return '\n'.join(out_lines)


# ───── разбивка на чанки ≤ 4096 символов (лимит Telegram) ─────
MAX_TG_LEN = 4096


def split_for_telegram(text: str, limit: int = MAX_TG_LEN) -> List[str]:
    """Делит текст на куски не больше limit символов, стараясь по \\n\\n."""
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    while len(text) > limit:
        # ищем последний \n\n или \n до лимита
        cut = text.rfind('\n\n', 0, limit)
        if cut < limit // 2:
            cut = text.rfind('\n', 0, limit)
        if cut < limit // 2:
            cut = text.rfind(' ', 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text.strip())
    return [p for p in parts if p]
