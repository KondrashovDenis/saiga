"""Тесты конвертера markdown → Telegram HTML.

Тестируем "контракт" функции: на каждый вход — фиксированный выход.
Если кто-то изменит логику — тесты упадут и подсветят что именно.
"""
import pytest
from utils.markdown_tg import (
    markdown_to_telegram_html,
    split_for_telegram,
    _esc,
    _inline,
    MAX_TG_LEN,
)


# ──────────────────────────── _esc ────────────────────────────
@pytest.mark.parametrize('inp, expected', [
    ('hello',           'hello'),
    ('a < b',           'a &lt; b'),
    ('a > b',           'a &gt; b'),
    ('a & b',           'a &amp; b'),
    ('<script>',        '&lt;script&gt;'),
    ('A & <b> & </b>',  'A &amp; &lt;b&gt; &amp; &lt;/b&gt;'),
    ('',                ''),
])
def test_esc(inp, expected):
    assert _esc(inp) == expected


# ──────────────────────────── _inline ────────────────────────────
class TestInline:
    """Inline-форматирование: bold, italic, code, links.

    Класс-обёртка нужен только для группировки в выводе pytest.
    """

    def test_bold(self):
        assert _inline('**hello**') == '<b>hello</b>'

    def test_italic_star(self):
        assert _inline('*it*') == '<i>it</i>'

    def test_italic_underscore(self):
        assert _inline('_it_') == '<i>it</i>'

    def test_inline_code(self):
        assert _inline('`x = 1`') == '<code>x = 1</code>'

    def test_link(self):
        assert _inline('[text](https://example.com)') == \
               '<a href="https://example.com">text</a>'

    def test_bold_inside_text(self):
        assert _inline('text **bold** rest') == 'text <b>bold</b> rest'

    def test_combined_bold_and_code(self):
        # bold не должен парситься внутри code
        assert _inline('`**not bold**`') == '<code>**not bold**</code>'

    def test_no_format(self):
        assert _inline('plain text 123') == 'plain text 123'


# ──────────────────────────── markdown_to_telegram_html ────────────────────────────
class TestMarkdown:
    def test_empty(self):
        assert markdown_to_telegram_html('') == ''

    def test_plain_text(self):
        assert markdown_to_telegram_html('Просто текст') == 'Просто текст'

    def test_heading_h1(self):
        # h1-h4 → <b>...</b>
        assert markdown_to_telegram_html('# Заголовок') == '<b>Заголовок</b>'

    def test_heading_h3(self):
        assert markdown_to_telegram_html('### Подзаголовок') == '<b>Подзаголовок</b>'

    def test_bullet(self):
        assert markdown_to_telegram_html('- пункт') == '• пункт'

    def test_bullet_with_star(self):
        assert markdown_to_telegram_html('* пункт') == '• пункт'

    def test_numbered(self):
        # нумерованный список просто оставляем — Telegram умеет цифры
        assert markdown_to_telegram_html('1. Раз') == '1. Раз'

    def test_html_escaped_in_plain(self):
        assert markdown_to_telegram_html('<script>') == '&lt;script&gt;'

    def test_html_escaped_in_heading(self):
        assert markdown_to_telegram_html('# <evil>') == '<b>&lt;evil&gt;</b>'

    def test_inline_inside_heading(self):
        # **bold** внутри ### должно работать
        assert markdown_to_telegram_html('### Раз **два** три') == \
               '<b>Раз <b>два</b> три</b>'

    def test_full_message(self):
        src = (
            "### Ингредиенты:\n"
            "- 250 г муки\n"
            "- 2 яйца\n"
        )
        out = markdown_to_telegram_html(src)
        assert '<b>Ингредиенты:</b>' in out
        assert '• 250 г муки' in out
        assert '• 2 яйца' in out

    def test_code_block(self):
        src = "```\nhello\nworld\n```"
        out = markdown_to_telegram_html(src)
        assert out == '<pre><code>hello\nworld</code></pre>'

    def test_code_block_with_lang(self):
        # Telegram не использует язык, но он не должен сломать парсинг
        src = "```python\nprint(1)\n```"
        out = markdown_to_telegram_html(src)
        assert '<pre><code>print(1)</code></pre>' == out

    def test_code_block_html_escaped(self):
        src = "```\n<script>\n```"
        out = markdown_to_telegram_html(src)
        assert '&lt;script&gt;' in out
        assert '<script>' not in out

    def test_link_in_text(self):
        out = markdown_to_telegram_html('Смотри [сюда](https://x.io) пожалуйста')
        assert '<a href="https://x.io">сюда</a>' in out


# ──────────────────────────── split_for_telegram ────────────────────────────
class TestSplit:
    def test_short_stays_one(self):
        assert split_for_telegram('hi') == ['hi']

    def test_exact_limit_stays_one(self):
        s = 'a' * MAX_TG_LEN
        assert split_for_telegram(s) == [s]

    def test_split_on_double_newline(self):
        # явный разделитель абзацев должен быть приоритетным
        chunks = split_for_telegram('a' * 50 + '\n\n' + 'b' * 50, limit=60)
        assert len(chunks) >= 2
        # каждый chunk в пределах limit
        assert all(len(c) <= 60 for c in chunks)

    def test_split_no_break_breaks_on_space(self):
        chunks = split_for_telegram('word ' * 200, limit=100)
        assert all(len(c) <= 100 for c in chunks)
        # ни один chunk не должен иметь пробел в конце или начале
        assert all(c == c.strip() for c in chunks)

    def test_huge_text(self):
        # Большой текст должен разбиться, ни один кусок не превысит лимит
        text = ('Это предложение. ' * 500)  # ~8500 символов
        chunks = split_for_telegram(text)
        assert len(chunks) >= 2
        assert all(len(c) <= MAX_TG_LEN for c in chunks)
