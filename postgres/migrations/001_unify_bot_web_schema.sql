-- Миграция 001: добавление колонок которые есть в bot/models, но не в web/models.
-- Применить вручную после инициализации БД через web (db.create_all создаёт схему web).
--
-- Применение:
--   docker exec -i saiga-postgres psql -U saiga_app -d saiga < postgres/migrations/001_unify_bot_web_schema.sql
--
-- TODO: перейти на Alembic миграции — тогда этот файл превратится в alembic/versions/001_*.py.

-- Conversations: бот использует is_active для архивации
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Messages: бот хранит metadata Telegram-сообщений
ALTER TABLE messages ADD COLUMN IF NOT EXISTS telegram_message_id INTEGER;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text';

-- Settings: бот пишет свои user-prefs (не пересекается с web UI-prefs)
ALTER TABLE settings ADD COLUMN IF NOT EXISTS max_tokens INTEGER DEFAULT 2048;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'ru';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS quick_replies_enabled BOOLEAN DEFAULT TRUE;
