"""initial unified schema

Revision ID: 0001
Revises:
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=True),
        sa.Column("email", sa.String(120), unique=True, nullable=True),
        sa.Column("password_hash", sa.String(256), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("telegram_username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(64), nullable=True),
        sa.Column("last_name", sa.String(64), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True, server_default="ru"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity", sa.DateTime(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("auth_method", sa.String(20), nullable=True, server_default="email"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="Новый диалог"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("share_token", sa.String(64), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(),
                  sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(20), nullable=True, server_default="text"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("ui_theme", sa.String(20), server_default="auto"),
        sa.Column("avatar_style", sa.String(20), server_default="initials"),
        sa.Column("message_animations", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("auto_scroll", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("show_timestamps", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("show_quick_replies", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("enable_reactions", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("markdown_support", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("quick_replies_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("temperature", sa.Float(), server_default="0.7"),
        sa.Column("top_p", sa.Float(), server_default="0.9"),
        sa.Column("max_tokens", sa.Integer(), server_default="2048"),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("model_preferences_json", sa.Text(), server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
