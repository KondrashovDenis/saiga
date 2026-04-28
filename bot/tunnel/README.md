# tunnel — autossh sidecar для бота

Бот живёт отдельно от Postgres (на homeserver-провайдере заблокирован
api.telegram.org, поэтому бот на отдельном хосте). Этот sidecar держит
SSH-туннель к удалённому PG.

## Установка (для self-hosting)

1. Сгенерировать ключ-пару только для туннеля:
   ```bash
   ssh-keygen -t ed25519 -f id_ed25519 -N ""
   ```
2. Добавить публичную часть на LLM-хост (`~/.ssh/authorized_keys` пользователя
   denciao) с ограничением:
   ```
   command="/bin/false",no-pty,no-X11-forwarding,no-agent-forwarding,no-user-rc,permitopen="127.0.0.1:5432" ssh-ed25519 AAA... saiga-bot-tunnel
   ```
   ⚠️ `permitopen` — обязательно с явным IP `127.0.0.1`, не `localhost`. И **не**
   используйте `restrict` — на OpenSSH 9.x в Debian 12 он ломает forwarding,
   и `permitopen` потом не override'ит. Список no-* опций перечислен явно.
3. `known_hosts` уже есть в репо (host key хост-сервера).
4. Если хост другой — обновите IP/порт в `Dockerfile` и `known_hosts`.

## Файлы

- `Dockerfile` — alpine + openssh-client + autossh
- `known_hosts` — host key целевого хоста (в репо, чтобы StrictHostKeyChecking=yes работал из коробки)
- `id_ed25519` — приватный ключ (в `.gitignore`, генерится локально)
