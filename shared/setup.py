from setuptools import setup, find_packages

setup(
    name="saiga_shared",
    version="0.2.0",
    description="Shared SQLAlchemy models for saiga web and bot (incl. RAG)",
    packages=find_packages(),
    install_requires=[
        "SQLAlchemy>=2.0,<3.0",
        # pgvector — только Python-пакет с SA типами (Vector, индексы),
        # серверный extension ставится в saiga-postgres (Dockerfile).
        # Маленький (~50 KB), нужен и web и bot чтобы импорт shared не падал.
        "pgvector>=0.3.6,<0.4",
    ],
    python_requires=">=3.10",
)
