# saiga-embedding

FastAPI-сервис, кладёт текст → 1024-мерный embedding-вектор через
`intfloat/multilingual-e5-large` на CPU. Используется saiga и (в будущем)
sochispirit-app для RAG.

## Endpoints

```
GET  /healthz
POST /embed        body={text:str, kind: "passage"|"query"}
POST /embed/batch  body={texts: [str], kind: "passage"|"query"}
```

Все POST требуют `Authorization: Bearer <EMBEDDING_API_KEY>`.

`kind`:
- `passage` — для индексируемых документов (default)
- `query` — для пользовательских запросов

E5-модели обучены на префиксах `passage:` / `query:`. Сервис добавляет их сам.

## Запуск

```bash
cp .env.example .env
# вписать EMBEDDING_API_KEY (openssl rand -hex 32)

docker compose --env-file .env up -d --build
```

Первый старт — медленный: качается ~2.2 GB весов в `embedding-models` volume.

## Проверка

```bash
# host shell, через docker network
docker run --rm --network saiga-internal curlimages/curl:8.10.1 \
    -fsS -X POST http://saiga-embedding:8000/embed \
    -H "Authorization: Bearer $EMBEDDING_API_KEY" \
    -H "content-type: application/json" \
    -d '{"text": "проверка", "kind": "query"}' | head -c 200
```
