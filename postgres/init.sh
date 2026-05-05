#!/bin/bash
# Запускается ОДИН РАЗ при первой инициализации БД (если volume пустой).
# Создаёт пользователей приложения и разделяет DDL/DML права.
#
# Пользователи:
#   saiga_admin (POSTGRES_USER) — суперюзер. Только для бэкапов и расширений.
#   saiga_migrator              — owner БД. DDL права. Используется только Alembic.
#   saiga_app                   — runtime web/bot. Только DML (SELECT/INSERT/UPDATE/DELETE).
#
# pgvector: extension создаётся под saiga_admin (требует superuser), потом
# Alembic под saiga_migrator создаёт таблицы с vector-колонками.
#
# Для существующих БД (init.sh уже отработал — volume не пустой) миграция
# прав делается одноразово вручную, см. /tmp/migrator_migrate.sql из 2026-05-05.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 1. saiga_migrator — owner БД, делает DDL через Alembic.
    CREATE USER saiga_migrator WITH PASSWORD '$SAIGA_MIGRATOR_PASSWORD';
    ALTER DATABASE $POSTGRES_DB OWNER TO saiga_migrator;
    GRANT ALL ON SCHEMA public TO saiga_migrator;

    -- 2. saiga_app — runtime, только DML.
    CREATE USER saiga_app WITH PASSWORD '$SAIGA_APP_PASSWORD';
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO saiga_app;
    GRANT USAGE ON SCHEMA public TO saiga_app;

    -- 3. Дефолты — когда saiga_migrator (owner) создаст новую таблицу через
    --    Alembic миграцию, saiga_app сразу получит DML без отдельного GRANT.
    ALTER DEFAULT PRIVILEGES FOR USER saiga_migrator IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO saiga_app;
    ALTER DEFAULT PRIVILEGES FOR USER saiga_migrator IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO saiga_app;

    -- 4. Запретить saiga_app создавать таблицы в public.
    REVOKE CREATE ON SCHEMA public FROM saiga_app;

    -- 5. pgvector — требует superuser. На существующих БД (init.sh уже
    --    отработал) extension включается разово вручную:
    --    docker exec saiga-postgres psql -U saiga_admin -d saiga \\
    --      -c "CREATE EXTENSION IF NOT EXISTS vector"
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "init.sh: saiga_migrator (DDL) + saiga_app (DML) created; pgvector enabled"
