FROM alpine:3.20

RUN apk add --no-cache openssh-client autossh netcat-openbsd

# Ключ id_ed25519 ожидается рядом (в build context). В репо он в .gitignore —
# для self-hosting сгенерите свой и добавьте в authorized_keys на LLM-хосте.
COPY id_ed25519 /root/.ssh/id_ed25519
COPY known_hosts /root/.ssh/known_hosts
RUN chmod 700 /root/.ssh && \
    chmod 600 /root/.ssh/id_ed25519 && \
    chmod 644 /root/.ssh/known_hosts

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD nc -z localhost 5432 || exit 1

# autossh параметры:
# -M 0                — без monitoring port (используем ServerAliveInterval вместо)
# ExitOnForwardFailure — упасть если permitopen не разрешает forward (быстрее
#                        видна проблема в логах, compose перезапустит)
# permitopen в authorized_keys на удалённой стороне ДОЛЖЕН быть "127.0.0.1:5432"
# (явный IP, не localhost — иначе не матчит).
CMD ["autossh", "-M", "0", "-N", "-T", \
     "-o", "ServerAliveInterval=30", \
     "-o", "ServerAliveCountMax=3", \
     "-o", "ExitOnForwardFailure=yes", \
     "-o", "StrictHostKeyChecking=yes", \
     "-o", "BatchMode=yes", \
     "-L", "0.0.0.0:5432:127.0.0.1:5432", \
     "-p", "2233", \
     "denciao@77.37.239.52"]
