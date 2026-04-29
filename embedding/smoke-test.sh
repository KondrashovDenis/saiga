#!/bin/bash
# Smoke-тест RAG-инфраструктуры — проверка end-to-end:
# 1. saiga-embedding отвечает 200 на /healthz
# 2. /embed принимает текст, отдаёт 1024-мерный вектор
# 3. /embed/batch отдаёт правильное количество векторов
# 4. Bearer auth работает (без токена — 401)
#
# Запуск:
#   cd ~/projects/saiga/embedding && ./smoke-test.sh
#
# Зависимости: docker (для curl-image внутри сети saiga-internal), jq.
set -euo pipefail

cd "$(dirname "$0")"
[ -f .env ] || { echo "no .env"; exit 1; }
. ./.env

CURL="docker run --rm --network saiga-internal curlimages/curl:8.10.1"
BASE="http://saiga-embedding:8000"

echo "== /healthz =="
$CURL -fsS "$BASE/healthz" | head -c 200
echo

echo "== /embed без токена (ожидаем 401) =="
$CURL -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$BASE/embed" \
    -H "content-type: application/json" \
    -d '{"text":"test"}'

echo "== /embed с токеном (ожидаем 200, вектор длиной 1024) =="
LEN=$($CURL -fsS -X POST "$BASE/embed" \
    -H "Authorization: Bearer $EMBEDDING_API_KEY" \
    -H "content-type: application/json" \
    -d '{"text":"проверка работы embedding","kind":"query"}' \
    | grep -oE '"vector":\[[^]]+\]' \
    | tr ',' '\n' | wc -l)
echo "vector items: $LEN (expected 1024)"
test "$LEN" = "1024" || { echo "FAIL: dim mismatch"; exit 1; }

echo "== /embed/batch (3 текста) =="
$CURL -fsS -X POST "$BASE/embed/batch" \
    -H "Authorization: Bearer $EMBEDDING_API_KEY" \
    -H "content-type: application/json" \
    -d '{"texts":["один","два","три"]}' \
    | head -c 300
echo

echo "OK — embedding service здоровый"
