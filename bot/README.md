# Saiga Telegram Bot

Telegram-бот для взаимодействия с языковой моделью Saiga Nemo 12B.

## Возможности

- 💬 Диалоги с AI-моделью
- 📁 Управление множественными диалогами  
- ⚙️ Персональные настройки
- 🎤 Голосовые сообщения
- 📄 Анализ документов (PDF, DOCX, TXT)
- 🔄 Синхронизация с веб-интерфейсом

## Быстрый запуск

1. Создайте бота через @BotFather
2. Отредактируйте `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   ADMIN_TELEGRAM_IDS=your_telegram_id
   ```
3. Запустите:
   ```bash
   docker-compose up -d
   ```

## Команды бота

- `/start` - Начать работу
- `/new` - Новый диалог
- `/list` - Мои диалоги
- `/settings` - Настройки
- `/help` - Помощь

## Структура проекта

```
saiga-telegram-bot/
├── src/                 # Исходный код
│   ├── handlers/        # Обработчики команд
│   ├── keyboards/       # Клавиатуры
│   ├── models/         # Модели данных
│   ├── utils/          # Утилиты
│   └── main.py         # Точка входа
├── docker-compose.yml  # Docker конфигурация
├── Dockerfile         # Образ контейнера
└── requirements.txt   # Python зависимости
```
