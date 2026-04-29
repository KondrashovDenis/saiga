#!/bin/bash
# Запускается ОДИН РАЗ при первой инициализации БД (если volume пустой).
# Создаёт пользователя приложения и делает его владельцем БД saiga.
#
# Привилегии:
#   saiga_admin (POSTGRES_USER) — суперюзер, для бэкапов/миграций
#   saiga_app                   — владелец БД saiga (web + bot пишут под ним)
#
# pgvector: extension создаётся под saiga_admin (требует superuser), а после
# этого таблицы / индексы создаются нашим Alembic под saiga_app — owner БД.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Пользователь приложения. Пароль из env $SAIGA_APP_PASSWORD.
    CREATE USER saiga_app WITH PASSWORD '$SAIGA_APP_PASSWORD';

    -- Владелец БД — для db.create_all() и DDL миграций.
    ALTER DATABASE $POSTGRES_DB OWNER TO saiga_app;
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO saiga_app;

    -- На существующую схему public — все права.
    GRANT ALL ON SCHEMA public TO saiga_app;

    -- pgvector — требует superuser. saiga_app не суперюзер, поэтому
    -- CREATE EXTENSION делаем здесь, под saiga_admin (POSTGRES_USER).
    -- На существующих БД (где init.sh уже отработал) extension включается
    -- разово вручную: docker exec saiga-postgres psql -U saiga_admin -d saiga -c "CREATE EXTENSION IF NOT EXISTS vector"
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "init.sh: saiga_app created, owner of $POSTGRES_DB; pgvector enabled"
