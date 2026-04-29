"""email_verified — флаг подтверждения email-адреса

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-29

Контекст:
- Telegram-юзеры (auth_method='telegram') email подтверждать не нужно — TG
  сам по себе верифицирован.
- Email/password юзеры — должны подтвердить через ссылку на email перед
  возможностью логина.

Существующие записи: для юзера id=1 (telegram-only) ставим email_verified=True
просто для консистентности (хотя для telegram это поле не используется в check'ах).
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )
    # Backfill: всем существующим юзерам — true (миграция, не должна ломать
    # текущих юзеров; новые регистрации будут получать default=false уже на
    # уровне Python-модели).
    op.execute("UPDATE users SET email_verified = TRUE")


def downgrade() -> None:
    op.drop_column("users", "email_verified")
