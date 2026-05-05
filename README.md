# Saiga — self-hosted LLM stack with Web and Telegram interfaces

[![CI](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml/badge.svg)](https://github.com/KondrashovDenis/saiga/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL 16](https://img.shields.io/badge/postgres-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Ruff](https://img.shields.io/badge/lint-ruff-d7ff64.svg)](https://github.com/astral-sh/ruff)

**English** · [Русский](README.ru.md)

A fully self-hostable stack built around **Saiga Nemo 12B** (Q4_K_M GGUF) — a Russian-language LLM:
local inference on CPU/GPU, web interface with authentication and shared settings, Telegram bot
linked to the same user account with shared conversations. Optional distributed deployment across
two hosts, observability via Prometheus + Grafana, error tracking via Sentry, CI/CD on GitHub Actions.

> Open source (MIT) — fork it, deploy your own, adapt to a different model. Works with any GGUF
> model, not just Saiga (just point `config.yaml` at it).

## Features

### Single account across Web and Telegram
- Email/password registration in Web
- Telegram linking via deep-link (no Telegram Login Widget — independent from `@BotFather`
  domain settings and Telegram-side caches)
- First-time login through Telegram (bot creates a user record, web gets a session cookie via poll)
- Shared conversations, history, and settings — both interfaces see the same data

### Generation parameters (synced)
- Temperature (0.1–2.0), Top P (0.1–1.0), Max Tokens (128–8192)
- Edited in the bot via `ConversationHandler` with validation
- Edited in the web via a form
- Single source of truth: one `Setting` row per user in DB

### Conversation management
- Auto-rename from the first user message
- `/rename <new title>` in bot, ✎ button in web
- `/list` in bot highlights the active conversation 🟢
- Full history retained without truncation

### Auth & security
- `scrypt` password hashing (Werkzeug 2.3.7) with rehash-on-login from legacy PBKDF2
- Email verification via signed token (1-day TTL)
- Forgot-password flow with reset-link (1-hour TTL, invalidates after password change)
- Telegram link confirmation step in bot — protects against intercepted link tokens
- Admin page with user management (toggle admin/verified, reset password, send reset email,
  delete with double confirmation)
- DDL/DML separation in Postgres: `_migrator` role for Alembic, `_app` role for runtime
  (DML only) — runtime cannot DROP/ALTER even if its credential leaks
- CSP `script-src 'self'` (no `unsafe-inline`)
- CSRF protection on all state-changing endpoints

### Observability
- Prometheus + Grafana, with Node Exporter, cAdvisor, and DCGM Exporter (NVIDIA GPU metrics)
- Sentry SDK in both web and bot — exceptions reported in real time with traceback
- Two-layer protection on metrics endpoint: HTTP basic_auth + Grafana login

### Reliability
- Auto-applied DB migrations on web container start (`alembic upgrade head`)
- Daily `pg_dumpall` backup with rotation (retain last 7)
- Telegram bot reconnects via `autossh` sidecar when reaching DB through SSH tunnel

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Primary host (LLM + Web)                    │
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
│     │                                 │ optional SSH tunnel      │
│     │                                 │ :5432 to bot host        │
└─────┼─────────────────────────────────┼──────────────────────────┘
      │                                 │
┌─────┼─────────────────────────────────┼──────────────────────────┐
│     │     Optional second host (bot)  │                          │
│     │                                 ▼                          │
│     │   ┌──────────┐    ┌──────────────────┐                     │
│     │   │  Redis   │◀───│  telegram bot    │                     │
│     │   └──────────┘    │ (python-tg-bot)  │                     │
│     │                   └────────┬─────────┘                     │
│     ▼                            ▼ HTTPS                         │
│  Telegram API ◀──────────── llm.<your-domain> + web.<domain>     │
└──────────────────────────────────────────────────────────────────┘
```

**Why two hosts (optional):** if your LLM host is on a network where `api.telegram.org` is
blocked or unreliable, the bot can run on a separate VPS and reach the LLM/Postgres through
the public domain (Bearer auth) and an SSH tunnel. If your network can reach Telegram directly,
run everything on a single host.

## Stack

| Layer | Technologies |
|---|---|
| LLM | text-generation-webui (oobabooga, pinned via submodule), llama.cpp, Saiga Nemo 12B (Q4_K_M GGUF) |
| Web | Python 3.11, Flask, Gunicorn, SQLAlchemy 2.0, Flask-Login, Postgres 16 |
| Bot | Python 3.11, python-telegram-bot 20.7, asyncpg, Redis |
| Migrations | Alembic |
| Proxy / TLS | Caddy 2 (auto Let's Encrypt) |
| Observability | Prometheus, Grafana, node-exporter, cAdvisor, DCGM-exporter, Sentry |
| CI | GitHub Actions, ruff, pytest, pytest-cov |

## Repository layout

```
saiga/
├── proxy/        Caddy 2 — reverse proxy + auto-LE
├── llm/          text-generation-webui (submodule) + GGUF models + nvidia-uvm.service
├── web/          Flask app, Dockerfile, entrypoint
├── postgres/     PG 16 + init.sh creating _migrator (DDL) and _app (DML) roles
├── monitoring/   Prometheus + Grafana + exporters
├── bot/          Telegram bot + tunnel/ sidecar (separate-host deploy)
└── shared/       Shared SQLAlchemy 2.0 models + Alembic migrations
```

## Self-hosting

> Minimum: 1 host with Docker, a domain with DNS A-record, GPU recommended (CPU works too).
> Telegram bot is optional.

### 1. Clone with submodules

```bash
git clone --recursive git@github.com:<your-fork>/saiga.git
cd saiga
```

### 2. Prepare `.env` files

Each service has an `.env.example`. Copy and fill in:

```bash
cp proxy/.env.example         proxy/.env
cp postgres/.env.example      postgres/.env
cp web/.env.example           web/.env
cp monitoring/.env.example    monitoring/.env
cp bot/.env.example           bot/.env  # on the bot host
```

Required values:

- `LE_EMAIL` — Let's Encrypt contact (`proxy/.env`)
- `LLM_API_KEY` — `openssl rand -hex 32`, used by Caddy and the bot
- `POSTGRES_PASSWORD`, `SAIGA_MIGRATOR_PASSWORD`, `SAIGA_APP_PASSWORD` — DB role passwords
- `MIGRATION_DATABASE_URL` (in `web/.env`) — DSN for Alembic, points at `_migrator` role
- `DATABASE_URL` (in `web/.env`) — DSN for runtime, points at `_app` role
- `SECRET_KEY` — Flask, `python -c "import secrets; print(secrets.token_hex(32))"`
- `TELEGRAM_BOT_TOKEN` — from `@BotFather` (only if running the bot)
- `TELEGRAM_BOT_USERNAME` — bot username without `@` (for deep-link login URLs)
- `SENTRY_DSN` — optional
- SMTP credentials — optional, needed for email verification and password reset
- `*_PASSWORD` — for Caddy basic_auth (`ui.*` and `metrics.*` subdomains)

### 3. Download a GGUF model

```bash
cd llm/models
wget https://huggingface.co/IlyaGusev/saiga_nemo_12b_gguf/resolve/main/saiga_nemo_12b.Q4_K_M.gguf
```

Set the model name/path in `llm/overlays/text-generation-webui/user_data/models/config.yaml`.

### 4. nvidia-uvm.service (for headless GPU servers)

```bash
sudo cp llm/systemd/nvidia-uvm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-uvm.service
```

Without this, after a reboot Docker `runtime: nvidia` cannot find the UVM device files.

### 5. Bring up the stack

```bash
# 1. Postgres first
cd postgres && docker compose --env-file .env up -d

# 2. LLM
cd ../llm && docker compose --env-file .env up -d

# 3. Web (entrypoint runs alembic upgrade head automatically)
cd ../web/docker && docker compose --env-file ../.env up -d

# 4. Caddy
cd ../../proxy && docker compose --env-file .env up -d

# 5. Observability (optional)
cd ../monitoring && docker compose --env-file .env up -d
```

### 6. Telegram bot (optional, can run on a separate host)

```bash
cd bot && docker compose --env-file .env up -d
```

If the bot runs on a different host than Postgres — set up the SSH tunnel
(see `bot/tunnel/README.md`).

## Tests

```bash
pip install -e ./shared
cd bot
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=src --cov-report=term
```

62 unit tests covering markdown→Telegram HTML conversion, async URL resolution, env validation,
edge cases, and the `TelegramLinkToken` model. Tests use SQLite, production uses PostgreSQL.

## Backup

```bash
./web/backup.sh   # pg_dumpall + retain last 7
```

The script keeps dumps under `<repo>/backups/`. Add to cron:

```bash
30 3 * * * /path/to/saiga/web/backup.sh >> /path/to/saiga/backups/backup.log 2>&1
```

## License

[MIT](LICENSE) — use, fork, modify, deploy commercially. Please keep the original copyright.

## Credits

- LLM — [IlyaGusev/saiga_nemo_12b](https://huggingface.co/IlyaGusev/saiga_nemo_12b)
- Inference — [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- GPU monitoring — [NVIDIA/dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter)
