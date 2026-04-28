# Saiga — self-hosted LLM-стек с веб- и Telegram-интерфейсами

![CI](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Self-hostable стек на основе **Saiga Nemo 12B** (Q4_K_M GGUF): LLM-инференс на CPU/GPU,
веб-интерфейс с авторизацией и общими настройками, Telegram-бот с тем же аккаунтом юзера и общими диалогами. Distributed deployment на 2 серверах, observability на Prometheus + Grafana, ошибки в Sentry, CI/CD на GitHub Actions.

> Open source (MIT) — форкайте, разворачивайте у себя, адаптируйте под свою модель. Подходит и для других GGUF-моделей кроме Saiga (правится один config.yaml).

**Демо:** [saiga.vaibkod.ru](https://saiga.vaibkod.ru) · бот: [@saiga_ai_bot](https://t.me/saiga_ai_bot)

## Что внутри

- **LLM-инференс** — `text-generation-webui` (llama.cpp) с layer offload на N×GPU. Вынесен в submodule, пинится на конкретный коммит апстрима.
- **Web** — Flask + Gunicorn + SQLAlchemy 2.0 + Postgres 16, тёмный sidebar UI с кастомным markdown-рендером (без Bootstrap). Auth: email/password + Telegram deep-link login.
- **Telegram-бот** — `python-telegram-bot` 20.7 (async), Redis для state, кастомный markdown→HTML конвертер для Telegram. **Один аккаунт юзера на бот и веб** — диалоги общие в обе стороны.
- **Унифицированные модели** — общий пакет `shared/saiga_shared/` (plain SQLAlchemy 2.0 DeclarativeBase), web и bot используют одну схему. Миграции — Alembic.
- **Observability** — Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter (NVIDIA GPU метрики), Sentry SDK в web и bot.
- **CI** — GitHub Actions: ruff + pytest + coverage (62 unit-теста).

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                        homeserver (LLM host)                     │
│                                                                  │
│  ┌──────┐    ┌─────────────┐    ┌────────────┐    ┌──────────┐   │
│  │Caddy │───▶│ saiga-web   │───▶│  Postgres  │    │saiga-llm │   │
│  │ :443 │    │ (Flask+gun) │    │   (PG 16)  │    │(text-gen │   │
│  └──┬───┘    └─────────────┘    └─────┬──────┘    │ -webui)  │   │
│     │                                 │           │  N×GPU   │   │
│     ├──── llm.vaibkod.ru (Bearer) ────────────────▶          │   │
│     ├──── saigaui.vaibkod.ru ────────────────────▶│ :5000    │   │
│     ├──── metrics.vaibkod.ru ────▶ Grafana        │ :7860    │   │
│     │                                 │           └──────────┘   │
│     │                                 │ SSH tunnel :5432         │
└─────┼─────────────────────────────────┼──────────────────────────┘
      │                                 │
┌─────┼─────────────────────────────────┼──────────────────────────┐
│     │     bot host (separate VPS)     │                          │
│     │                                 ▼                          │
│     │   ┌──────────┐    ┌──────────────────┐                     │
│     │   │  Redis   │◀───│ saiga-tg-bot     │                     │
│     │   └──────────┘    │ (python-tg-bot)  │                     │
│     │                   └────────┬─────────┘                     │
│     ▼                            ▼ HTTPS                         │
│  Telegram API ◀───────────── llm.vaibkod.ru / saiga.vaibkod.ru   │
└──────────────────────────────────────────────────────────────────┘
```

**Зачем 2 сервера:** на нашем homeserver-провайдере заблокирован `api.telegram.org`,
поэтому бот живёт на отдельном хосте и ходит к LLM/PG через публичный домен (Bearer auth)
и SSH-туннель. Если у вас провайдер не блокирует Telegram — всё можно поднять на одном хосте.

## Ключевые фичи

### Единый аккаунт web ↔ bot
- Email/password регистрация в веб
- Привязка Telegram через deep-link (без Telegram Login Widget — не зависит от domain в @BotFather и кэшей Telegram)
- Первичный вход через Telegram (бот создаёт юзера в БД, веб получает session-cookie через poll)
- Диалоги, история, настройки — общие

### Настройки генерации
- Temperature (0.1–2.0), Top P (0.1–1.0), Max Tokens (128–8192)
- Меняются в боте через ConversationHandler с валидацией
- Меняются в веб через форму
- Применяются и в боте и в веб (одна модель `Setting` в БД)

### Diff-management
- Auto-rename диалога по первому user-сообщению
- `/rename <new title>` в боте, кнопка ✎ в веб
- `/list` в боте показывает активный диалог 🟢
- История с полным контекстом, без обрезаний

### Observability
- 5 контейнеров мониторинга, 3 Grafana dashboards (Node Exporter Full, NVIDIA DCGM, кастомный Docker)
- Sentry в web и bot — ошибки шлются в реальном времени с traceback'ом
- Caddy basic_auth + Grafana login = двухслойная защита `metrics.vaibkod.ru`

## Стек

| Компонент | Технологии |
|---|---|
| LLM | text-generation-webui, llama.cpp, Saiga Nemo 12B (Q4_K_M GGUF) |
| Web | Python 3.11, Flask, Gunicorn, SQLAlchemy 2.0, Flask-Login, Postgres 16 |
| Bot | Python 3.11, python-telegram-bot 20.7, asyncpg, Redis |
| Migrations | Alembic |
| Proxy | Caddy 2 (auto-LE TLS) |
| Observability | Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter, Sentry |
| CI | GitHub Actions, ruff, pytest, pytest-cov |

## Раскладка по серверам

```
saiga/
├── proxy/        Caddy 2 — reverse proxy + auto-LE
├── llm/          text-generation-webui (submodule) + GGUF-модели + systemd-юнит для UVM
├── web/          Flask app
├── postgres/     PG 16 + init-script для saiga_app user
├── monitoring/   Prometheus + Grafana + exporters
├── bot/          Telegram bot (запускается на отдельном хосте) + tunnel/ sidecar
└── shared/       Общие модели + Alembic миграции
```

## Self-hosting: как развернуть у себя

> Минимум: 1 сервер с Docker, домен с DNS A-record, GPU желателен (можно CPU). Telegram-бот опционален.

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

Что заполнить:
- `LE_EMAIL` — для LetsEncrypt (`proxy/.env`)
- `LLM_API_KEY` — `openssl rand -hex 32`, ходит в Caddy и в bot
- `POSTGRES_PASSWORD`, `SAIGA_APP_PASSWORD` — пароли PG (admin и app user)
- `SECRET_KEY` — Flask, `python -c 'import secrets;print(secrets.token_hex(32))'`
- `TELEGRAM_BOT_TOKEN` — от `@BotFather` (если используешь бота)
- `TELEGRAM_BOT_USERNAME` — username бота без `@` (для deep-link login)
- `SENTRY_DSN` — опционально
- `*_PASSWORD` — для basic_auth в Caddy (`saigaui` и `metrics`)

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

Без этого после ребута `runtime: nvidia` не находит UVM device files.

### 5. Поднять стек

```bash
# 1. Postgres первым
cd postgres && docker compose --env-file .env up -d

# 2. LLM
cd ../llm && docker compose --env-file .env up -d

# 3. Web (entrypoint автоматически прогонит alembic upgrade head)
cd ../web/docker && docker compose --env-file ../.env up -d

# 4. Caddy
cd ../../proxy && docker compose --env-file .env up -d

# 5. Observability (опционально)
cd ../monitoring && docker compose --env-file .env up -d
```

### 6. Бот (отдельно, опционально)

На том же или отдельном хосте:

```bash
cd bot && docker compose --env-file .env up -d
```

Если бот живёт **отдельно** от LLM — нужен SSH-туннель к Postgres
(см. `bot/tunnel/README.md`).

## Тесты

```bash
pip install -e ./shared
cd bot
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=src --cov-report=term
```

62 теста: markdown→TG HTML конвертер, async URL-резолвинг, валидация env, edge cases,
TelegramLinkToken model. Тесты используют SQLite, в проде — PG.

## Backup

```bash
./web/backup.sh   # pg_dumpall + ротация 7 последних
```

Скрипт держит дампы в `~/projects/saiga/backups/`. Под cron:

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
