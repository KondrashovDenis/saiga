# Postgres 16 + pgvector v0.8.0 на alpine.
#
# Зачем кастомный образ: ванильный postgres:16-alpine не содержит pgvector,
# а в pg_available_extensions у нас он не появляется. RAG-инфраструктура (для
# saiga knowledge base и для будущего sochispirit-app) требует vector-типа
# и индексов HNSW/IVFFlat.
#
# Грабли alpine 3.23 toolchain mismatch:
#   - В postgres:16-alpine pgxs Makefile.global ЖЁСТКО зашит на:
#     CLANG = clang-19 + /usr/lib/llvm19/bin/llvm-lto (для thinLTO bitcode)
#   - Но JIT runtime (postgresql16-jit) использует libLLVM-16.so
#   - Решение: ставим оба toolchain'а — clang16 (для генерации LLVM-16 bitcode,
#     совместимого с runtime libLLVM-16.so) + llvm19 (для llvm-lto-19 утилиты).
#     LLVM bitcode forward-compatible — llvm-lto-19 спокойно линкует .bc от clang-16.
#   - В make передаём CLANG=clang-16 — обходим зашитый clang-19.
#
# Размер итогового образа ~150 MB (после `apk del .build-deps` toolchain
# выпиливается, остаётся только vector.so + .bc файлы для JIT).
FROM postgres:16-alpine

ARG PGVECTOR_REF=v0.8.0

# Шаг 1: build-toolchain. Долгий слой (~22 мин на медленном диске),
# но сохраняется в кеше docker buildkit между сборками. Ставим И clang16
# (для bitcode runtime-совместимого с libLLVM-16) И llvm19 (для llvm-lto-19,
# который Makefile.global вызывает по абсолютному пути).
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    clang16 \
    llvm16-dev \
    llvm19 \
    postgresql16-dev \
    git

# Шаг 2: clone + compile + install.
# CLANG=clang-16 — обходим зашитый clang-19 в Makefile.global; bitcode
# совместим с runtime libLLVM-16.so. Линковка через llvm-lto-19 — OK,
# bitcode forward-compatible.
RUN set -eux; \
    cd /tmp; \
    git clone --depth 1 --branch ${PGVECTOR_REF} https://github.com/pgvector/pgvector.git; \
    cd pgvector; \
    make CLANG=clang-16 OPTFLAGS=""; \
    make CLANG=clang-16 install; \
    cd /; \
    rm -rf /tmp/pgvector

# Шаг 3: убираем build-deps. Финальный layer только с runtime артефактами
# pgvector — ужимает образ обратно к ~150 MB.
RUN apk del .build-deps
