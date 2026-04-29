"""rag_foundation — knowledge_bases / documents / chunks (pgvector)

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-29

CREATE EXTENSION vector НЕ делается здесь (Alembic запускается под saiga_app
— не суперюзер). Extension включается отдельно — через init.sh при первой
инициализации БД (для fresh deployments) или вручную:

    docker exec saiga-postgres psql -U saiga_admin -d saiga \\
        -c "CREATE EXTENSION IF NOT EXISTS vector"

Если миграция упадёт на vector(1024) с "type not exists" — значит extension
не включён, см. выше.

HNSW-индекс по chunks.embedding с vector_cosine_ops — чтобы запросы
"ORDER BY embedding <=> :query" работали быстро (O(log n) вместо full scan).
m=16, ef_construction=64 — defaults pgvector, балансируют скорость/точность.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


CHUNK_DIM = 1024


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("owner_id", "slug", name="uq_kb_owner_slug"),
    )
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kb_id", sa.Integer(),
                  sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_documents_kb_id", "documents", ["kb_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(CHUNK_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    # HNSW индекс — быстрая ANN-search через cosine distance.
    # vector_cosine_ops подходит для нормализованных векторов (наши e5
    # нормализуются в embedding service, см. app.py).
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_kb_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
