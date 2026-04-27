"""conftest.py — выполняется pytest ДО сбора тестов и до любых импортов из them.

Зачем нужен: src/config.py при импорте сразу резолвит обязательные env через
_required('TELEGRAM_BOT_TOKEN') и _required('DATABASE_URL'). В тестовом окружении
этих переменных нет, и любой 'from config import ...' падает с RuntimeError.

Решение: подкладываем фейковые значения тут, до того как тесты начнут импортить
свои модули. Реальные тесты на _required всё равно работают через monkeypatch
(он временно меняет env только на время одного теста).
"""
import os

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test:test')
os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/saiga-bot-test.db')
os.environ.setdefault('ADMIN_TELEGRAM_IDS', '0')
