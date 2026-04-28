# Saiga

![CI](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Self-hostable стек на основе **Saiga Nemo 12B** (Q4_K_M GGUF): LLM-инференс на CPU/GPU, веб-интерфейс с авторизацией и Telegram-бот. Распределённый деплой на двух серверах, observability на Prometheus + Grafana, Sentry для ошибок.

> Open source (MIT) — форкайте, разворачивайте у себя, адаптируйте под свою модель. Подходит и для других GGUF-моделей кроме Saiga.

## Что внутри

- **LLM-инференс** — `text-generation-webui` (llama.cpp) с layer offload на N×GPU
- **Web** — Flask + Gunicorn + SQLAlchemy + Postgres 16, тёмный sidebar UI с кастомным markdown-рендером (без Bootstrap)
- **Telegram-бот** — `python-telegram-bot` 20.7 (async), Redis для state, кастомный markdown→HTML конвертер для Telegram
- **Observability** — Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter (NVIDIA GPU метрики), Sentry SDK в web и bot
- **CI** — GitHub Actions: ruff + pytest + coverage (52 unit-теста)

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
      │                                 │
┌─────┼─────────────────────────────────┼──────────────────────────┐
│     │     debianOCR (bot host)        │                          │
│     │                                 ▼                          │
│     │   ┌──────────┐    ┌──────────────────┐                     │
│     │   │  Redis   │◀───│ saiga-tg-bot     │                     │
│     │   └──────────┘    │ (python-tg-bot)  │                     │
│     │                   └────────┬─────────┘                     │
│     │                            │                               │
│     ▼                            ▼ HTTPS                         │
│  Telegram API ◀───────────── llm.vaibkod.ru / saiga.vaibkod.ru   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Зачем 2 сервера:** на homeserver-провайдере заблокирован `api.telegram.org`, поэтому бот живёт отдельно и ходит к LLM/PG через публичный домен (Bearer auth) и SSH-туннель.

## Стек

| Компонент | Технологии |
|---|---|
| LLM | text-generation-webui, llama.cpp, Saiga Nemo 12B (Q4_K_M GGUF) |
| Web | Python 3.11, Flask, Gunicorn, SQLAlchemy, Flask-Login, Postgres 16 |
| Bot | Python 3.11, python-telegram-bot 20.7, aiogram-style state, Redis |
| Proxy | Caddy 2 (auto-LE TLS) |
| Observability | Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter, Sentry |
| CI | GitHub Actions, ruff, pytest, pytest-cov |

## Раскладка по серверам

```
saiga/
├── proxy/        Caddy 2 — reverse proxy + auto-LE для всех субдоменов
├── llm/          text-generation-webui + GGUF-модели
├── web/          Flask app + Postgres
├── postgres/     PG 16 + миграции + init-script для saiga_app user
├── monitoring/   Prometheus + Grafana + exporters
└── bot/          Telegram bot (исходник; запускается на отдельном хосте)
```

## Self-hosting: как развернуть у себя

> Минимум: 1 сервер с Docker, домен с DNS A-record, GPU желателен (можно CPU). Telegram-бот опционален.


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
- `SENTRY_DSN` — опционально (для error tracking)
- `*_PASSWORD` — для basic_auth в Caddy (`saigaui` и `metrics`)

### 3. Скачать GGUF-модель

```bash
cd llm/models
# Saiga Nemo 12B (или любая другая GGUF-модель — поправь config.yaml)
wget https://huggingface.co/IlyaGusev/saiga_nemo_12b_gguf/resolve/main/saiga_nemo_12b.Q4_K_M.gguf
```

Имя модели в `llm/overlays/text-generation-webui/user_data/models/config.yaml`.

### 4. Поднять стек (на LLM-хосте)

```bash
# 1. Postgres первым (нужен для web и bot)
cd postgres && docker compose --env-file .env up -d

# 2. Применить миграции (см. ниже)
docker exec -i saiga-postgres psql -U saiga_app -d saiga < migrations/001_unify_bot_web_schema.sql

# 3. LLM
cd ../llm && docker compose --env-file .env up -d

# 4. Web
cd ../web/docker && docker compose --env-file ../.env up -d

# 5. Caddy (внешняя точка входа)
cd ../../proxy && docker compose --env-file .env up -d

# 6. Observability (опционально)
cd ../monitoring && docker compose --env-file .env up -d
```

### 5. Бот (отдельно, опционально)

На том же или отдельном хосте:

```bash
cd bot && docker compose --env-file .env up -d
```

Если бот живёт **отдельно** от LLM — нужен SSH-туннель к Postgres. См. секцию ниже.

## SSH-туннель к Postgres (для распределённого деплоя)

Если бот живёт не на LLM-хосте, ему нужен доступ к PG. Делается через restricted SSH-key:

1. На bot-хосте:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/saiga-tunnel -N ""
   ```

2. На LLM-хосте, в `~/.ssh/authorized_keys` добавить:
   ```
   command="/bin/false",no-pty,no-X11-forwarding,no-agent-forwarding,no-user-rc,permitopen="127.0.0.1:5432" ssh-ed25519 AAA... saiga-tunnel
   ```
   > **Важно:** `restrict` + `permitopen` ломается на OpenSSH 9.x в Debian 12 (`restrict` отключает forwarding, `permitopen` потом не override'ит). Пишите no-* опции вручную.

3. Sidecar `saiga-tunnel` (уже в `bot/docker-compose.yml`) — autossh-контейнер, держит туннель живым.

## Postgres user model

- `saiga_admin` — суперюзер (бэкапы, миграции). Из `POSTGRES_USER`.
- `saiga_app` — owner БД `saiga`, не суперюзер. Под ним работают web и bot.

`postgres/init.sh` (через `docker-entrypoint-initdb.d/`) создаёт `saiga_app` при первой инициализации БД.

## Тесты

```bash
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=src --cov-report=term-missing
```

52 теста: markdown→TG HTML конвертер, async URL-резолвинг, валидация env, edge cases. Тесты используют SQLite, в проде — PG.

## Backup

```bash
docker exec saiga-postgres pg_dump -U saiga_admin -d saiga | gzip > saiga_$(date +%F).sql.gz
```

(скрипт в `web/backup.sh` — переписан под pg_dump)

## Лицензия

[MIT](LICENSE) — используйте, форкайте, модифицируйте, разворачивайте коммерчески. Просьба — оставлять копирайт автора.

## Авторы и благодарности

- LLM — [IlyaGusev/saiga_nemo_12b](https://huggingface.co/IlyaGusev/saiga_nemo_12b) (фантастическая русскоязычная модель)
- Inference — [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- GPU мониторинг — [NVIDIA/dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter)
