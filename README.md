# Saiga

Локальная LLM на базе **Saiga Nemo 12B** (Q4_K_M GGUF) с веб-интерфейсом и Telegram-ботом. Работает на homeserver на 3 GPU через Docker.

## Архитектура

```
┌────────────────┐         ┌──────────────────────┐
│  Telegram      │ ──API── │  saiga-telegram-bot  │
│  (users)       │         │  (python-tg-bot)     │
└────────────────┘         └──────────┬───────────┘
                                      │
┌────────────────┐                    │
│  Browser       │ ──HTTPS──┐         │
│  saiga.        │          ▼         ▼
│  denciaopin    │      ┌──────────────────────┐
│  .com          │ ──── │   saiga-web-app      │
└────────────────┘      │   (Flask + SQLite)   │
                        └──────────┬───────────┘
                                   │ shared-saiga-db
                                   │ (SQLite, общий volume)
                                   │
                        ┌──────────▼───────────┐
                        │      saiga-llm       │
                        │ text-generation-webui│
                        │  + saiga_nemo_12b    │
                        │  GGUF Q4_K_M, 3 GPU  │
                        │  API :5000  UI :7860 │
                        └──────────────────────┘
```

## Структура

```
saiga/
├── llm/        Inference (text-generation-webui + GGUF модели)
├── web/        Flask веб-морда — saiga.denciaopin.com
├── bot/        Telegram-бот
└── README.md
```

Подробности по каждому компоненту — в его README.

## Запуск

```bash
# 1. LLM первым — другие сервисы зависят от его API
cd ~/projects/saiga/llm
docker compose up -d

# 2. Web и bot
cd ~/projects/saiga/web/docker && docker compose up -d
cd ~/projects/saiga/bot && docker compose up -d
```

## Внешние зависимости

- **Docker network `nginx-proxy`** (external) — общий контур для всех сервисов
- **Docker volume `shared-saiga-db`** (external) — общая SQLite БД для web и bot
- **GPU** — биндятся `/dev/nvidia0/1/2` + nvidia-smi и драйверные библиотеки с хоста

## Настройка секретов

В `bot/.env` и `web/.env` — токены Telegram-бота и Flask SECRET_KEY. Шаблоны в `*/​.env.example`. Реальные `.env` в `.gitignore`.

## Образы Docker (переиспользуем существующие)

| Сервис | Образ |
|---|---|
| `saiga-llm` | `llm-docker-saiga:latest` (32 GB, CUDA 11.8 + text-generation-webui) |
| `saiga-web-app` | `docker-saiga-web-app:latest` (246 MB) |
| `saiga-telegram-bot` | `saiga-telegram-bot-saiga-telegram-bot:latest` (864 MB) |

Compose-файлы используют `pull_policy: never` — пересборка не запускается. Для пересборки см. секцию ниже.

## Пересборка LLM-образа

`llm/text-generation-webui/` исключён из репозитория и должен подтягиваться как git submodule на форк апстрима [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui) (закреплён на коммите `ace8afb`). Локальный патч `user_data/models/config.yaml` лежит в `llm/overlays/text-generation-webui/...` и накатывается поверх submodule в Dockerfile.

> TODO: подключить submodule и обновить Dockerfile чтобы overlay копировался поверх submodule.
