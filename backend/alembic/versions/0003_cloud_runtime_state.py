"""Add cloud-safe runtime state and embedding provenance.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-13
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column(
            "embedding_model",
            sa.String(length=100),
            server_default=sa.text("'all-MiniLM-L6-v2'"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_articles_embedding_model",
        "articles",
        ["embedding_model"],
    )
    op.create_table(
        "groq_quota_usage",
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("usage_date"),
    )
    op.create_table(
        "quiz_sessions",
        sa.Column(
            "article_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("article_id"),
    )
    op.create_index(
        "idx_quiz_sessions_expires_at",
        "quiz_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_quiz_sessions_expires_at",
        table_name="quiz_sessions",
    )
    op.drop_table("quiz_sessions")
    op.drop_table("groq_quota_usage")
    op.drop_index(
        "idx_articles_embedding_model",
        table_name="articles",
    )
    op.drop_column("articles", "embedding_model")
