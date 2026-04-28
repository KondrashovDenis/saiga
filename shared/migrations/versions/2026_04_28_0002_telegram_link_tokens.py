"""telegram_link_tokens — одноразовые токены для deep-link login/привязки

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),  # 'link' | 'login'
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_telegram_link_tokens_token", "telegram_link_tokens", ["token"], unique=True
    )
    op.create_index(
        "ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_index("ix_telegram_link_tokens_token", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
