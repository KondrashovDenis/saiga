# Saiga — self-hosted LLM-стек с веб- и Telegram-интерфейсами

[![CI](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml/badge.svg)](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL 16](https://img.shields.io/badge/postgres-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Ruff](https://img.shields.io/badge/lint-ruff-d7ff64.svg)](https://github.com/astral-sh/ruff)

[English](README.md) · **Русский**

Self-hostable стек на основе **Saiga Nemo 12B** (Q4_K_M GGUF) — русскоязычной LLM:
локальный инференс на CPU/GPU, веб-интерфейс с авторизацией и общими настройками,
Telegram-бот привязанный к тому же аккаунту с общими диалогами. Опциональный
distributed deployment на двух хостах, observability на Prometheus + Grafana,
ошибки в Sentry, CI/CD на GitHub Actions.

> Open source (MIT) — форкайте, разворачивайте у себя, адаптируйте под свою модель.
> Подходит для любой GGUF-модели, не только Saiga (правится `config.yaml`).

## Возможности

### Единый аккаунт Web ↔ Telegram
- Регистрация по email/паролю в веб
- Привязка Telegram через deep-link (без Telegram Login Widget — не зависит от
  domain в `@BotFather` и кэшей Telegram)
- Первичный вход через Telegram (бот создаёт юзера в БД, веб получает session-cookie через poll)
- Диалоги, история, настройки — общие в обе стороны

### Параметры генерации (синхронизированы)
- Temperature (0.1–2.0), Top P (0.1–1.0), Max Tokens (128–8192)
- Меняются в боте через `ConversationHandler` с валидацией
- Меняются в веб через форму
- Один источник правды: одна запись `Setting` на юзера в БД

### Управление диалогами
- Auto-rename по первому user-сообщению
- `/rename <новое имя>` в боте, кнопка ✎ в веб
- `/list` в боте подсвечивает активный диалог 🟢
- Полная история без обрезаний

### Auth & безопасность
- Хеширование паролей `scrypt` (Werkzeug 2.3.7) с автоматическим rehash при логине из старого PBKDF2
- Подтверждение email signed-токеном (TTL 24 часа)
- Восстановление пароля через reset-link (TTL 1 час, инвалидируется после смены)
- Подтверждение привязки Telegram в боте — защита от перехваченных link-токенов
- Админ-страница с управлением юзерами (toggle admin/verified, reset password, send reset email,
  удаление с двойным подтверждением)
- Разделение DDL/DML в Postgres: роль `_migrator` для Alembic, `_app` для runtime (только DML) —
  runtime не может DROP/ALTER даже если её секрет утечёт
- CSP `script-src 'self'` (без `unsafe-inline`)
- CSRF-защита на всех state-changing endpoints

### Observability
- Prometheus + Grafana, с Node Exporter, cAdvisor, DCGM-exporter (метрики NVIDIA GPU)
- Sentry SDK в web и bot — ошибки в реальном времени с traceback
- Двухслойная защита metrics-эндпоинта: HTTP basic_auth + Grafana login

### Надёжность
- Авто-применение миграций при старте web-контейнера (`alembic upgrade head`)
- Ежедневный `pg_dumpall` бэкап с ротацией (последние 7)
- Telegram-бот переподключается через `autossh` sidecar, когда ходит к БД через SSH-туннель

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                     Основной хост (LLM + Web)                    │
│                                                                  │
│  ┌──────┐    ┌─────────────┐    ┌────────────┐    ┌──────────┐   │
│  │Caddy │───▶│   web       │───▶│  Postgres  │    │   llm    │   │
│  │ :443 │    │ Flask + gun │    │   (PG 16)  │    │ text-gen │   │
│  └──┬───┘    └─────────────┘    └─────┬──────┘    │  -webui  │   │
│     │                                 │           │  N×GPU   │   │
│     ├── llm.<your-domain> (Bearer) ───────────────▶ :5000    │   │
│     ├── ui.<your-domain>   (basic_auth) ─────────▶│ :7860    │   │
│     ├── metrics.<your-domain> ────▶ Grafana       │          │   │
│     │                                 │           └──────────┘   │
│     │                                 │ опциональный SSH-туннель │
│     │                                 │ :5432 к bot-хосту        │
└─────┼─────────────────────────────────┼──────────────────────────┘
      │                                 │
┌─────┼─────────────────────────────────┼──────────────────────────┐
│     │  Опциональный второй хост (бот) │                          │
│     │                                 ▼                          │
│     │   ┌──────────┐    ┌──────────────────┐                     │
│     │   │  Redis   │◀───│  telegram bot    │                     │
│     │   └──────────┘    │ (python-tg-bot)  │                     │
│     │                   └────────┬─────────┘                     │
│     ▼                            ▼ HTTPS                         │
│  Telegram API ◀──────────── llm.<your-domain> + web.<domain>     │
└──────────────────────────────────────────────────────────────────┘
```

**Зачем второй хост (опционально):** если на хосте с LLM сеть, где `api.telegram.org`
заблокирован или нестабилен, бот можно вынести на отдельный VPS — он будет ходить к
LLM/Postgres через публичный домен (Bearer auth) и SSH-туннель. Если сеть видит
Telegram напрямую — всё поднимается на одном хосте.

## Стек

| Слой | Технологии |
|---|---|
| LLM | text-generation-webui (oobabooga, через submodule), llama.cpp, Saiga Nemo 12B (Q4_K_M GGUF) |
| Web | Python 3.11, Flask, Gunicorn, SQLAlchemy 2.0, Flask-Login, Postgres 16 |
| Bot | Python 3.11, python-telegram-bot 20.7, asyncpg, Redis |
| Migrations | Alembic |
| Proxy / TLS | Caddy 2 (auto Let's Encrypt) |
| Observability | Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter, Sentry |
| CI | GitHub Actions, ruff, pytest, pytest-cov |

## Структура репозитория

```
saiga/
├── proxy/        Caddy 2 — reverse proxy + auto-LE
├── llm/          text-generation-webui (submodule) + GGUF-модели + nvidia-uvm.service
├── web/          Flask app, Dockerfile, entrypoint
├── postgres/     PG 16 + init.sh создающий роли _migrator (DDL) и _app (DML)
├── monitoring/   Prometheus + Grafana + exporters
├── bot/          Telegram bot + tunnel/ sidecar (для разнесённого деплоя)
└── shared/       Общие SQLAlchemy 2.0 модели + Alembic миграции
```

## Self-hosting: как развернуть у себя

> Минимум: 1 хост с Docker, домен с DNS A-записью, желателен GPU (можно CPU).
> Telegram-бот — опционально.

### 1. Клонировать с submodules

```bash
git clone --recursive git@github.com:<your-fork>/saiga.git
cd saiga
```

### 2. Подготовить `.env` файлы

В каждом сервисе есть `.env.example`. Скопируй и заполни:

```bash
cp proxy/.env.example         proxy/.env
cp postgres/.env.example      postgres/.env
cp web/.env.example           web/.env
cp monitoring/.env.example    monitoring/.env
cp bot/.env.example           bot/.env  # на bot-хосте
```

Что обязательно заполнить:

- `LE_EMAIL` — для Let's Encrypt (`proxy/.env`)
- `LLM_API_KEY` — `openssl rand -hex 32`, ходит в Caddy и в bot
- `POSTGRES_PASSWORD`, `SAIGA_MIGRATOR_PASSWORD`, `SAIGA_APP_PASSWORD` — пароли DB-ролей
- `MIGRATION_DATABASE_URL` (в `web/.env`) — DSN для Alembic, под ролью `_migrator`
- `DATABASE_URL` (в `web/.env`) — DSN для runtime, под ролью `_app`
- `SECRET_KEY` — Flask, `python -c "import secrets; print(secrets.token_hex(32))"`
- `TELEGRAM_BOT_TOKEN` — от `@BotFather` (если запускаешь бот)
- `TELEGRAM_BOT_USERNAME` — username бота без `@` (для deep-link login URL)
- `SENTRY_DSN` — опционально
- SMTP-credentials — опционально, нужны для email-верификации и password reset
- `*_PASSWORD` — для basic_auth в Caddy (поддомены `ui.*` и `metrics.*`)

### 3. Скачать GGUF-модель

```bash
cd llm/models
wget https://huggingface.co/IlyaGusev/saiga_nemo_12b_gguf/resolve/main/saiga_nemo_12b.Q4_K_M.gguf
```

Имя/путь модели — в `llm/overlays/text-generation-webui/user_data/models/config.yaml`.

### 4. nvidia-uvm.service (для headless серверов с GPU)

```bash
sudo cp llm/systemd/nvidia-uvm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-uvm.service
```

Без этого после ребута Docker `runtime: nvidia` не найдёт UVM device files.

### 5. Поднять стек

```bash
# 1. Postgres первым
cd postgres && docker compose --env-file .env up -d

# 2. LLM
cd ../llm && docker compose --env-file .env up -d

# 3. Web (entrypoint автоматически прогоняет alembic upgrade head)
cd ../web/docker && docker compose --env-file ../.env up -d

# 4. Caddy
cd ../../proxy && docker compose --env-file .env up -d

# 5. Observability (опционально)
cd ../monitoring && docker compose --env-file .env up -d
```

### 6. Telegram-бот (опционально, можно на отдельном хосте)

```bash
cd bot && docker compose --env-file .env up -d
```

Если бот живёт **отдельно** от Postgres — настрой SSH-туннель
(см. `bot/tunnel/README.md`).

## Тесты

```bash
pip install -e ./shared
cd bot
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=src --cov-report=term
```

62 unit-теста: markdown→Telegram HTML конвертер, async URL-резолвинг, валидация env,
edge cases, модель `TelegramLinkToken`. Тесты используют SQLite, в проде — PostgreSQL.

## Backup

```bash
./web/backup.sh   # pg_dumpall + ротация последних 7
```

Скрипт держит дампы в `<repo>/backups/`. Под cron:

```bash
30 3 * * * /path/to/saiga/web/backup.sh >> /path/to/saiga/backups/backup.log 2>&1
```

## Лицензия

[MIT](LICENSE) — используйте, форкайте, модифицируйте, разворачивайте коммерчески.
Просьба — оставлять копирайт автора.

## Авторы и благодарности

- LLM — [IlyaGusev/saiga_nemo_12b](https://huggingface.co/IlyaGusev/saiga_nemo_12b) (фантастическая русскоязычная модель)
- Inference — [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- GPU мониторинг — [NVIDIA/dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter)
