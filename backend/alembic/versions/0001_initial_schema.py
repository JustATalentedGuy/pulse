"""Create the initial Pulse schema.

Revision ID: 0001
Revises:
Create Date: 2026-06-11
"""
from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("importance", sa.SmallInteger(), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("embedding", Vector(dim=384), nullable=True),
        sa.Column(
            "enrichment_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "enrichment_attempts",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("enrichment_error", sa.Text(), nullable=True),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_duration_s", sa.Integer(), nullable=True),
        sa.Column(
            "bookmarked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("bookmarked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "quiz_attempted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("quiz_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column(
            "hidden",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index(
        "idx_articles_ingested_at", "articles", [sa.text("ingested_at DESC")]
    )
    op.create_index("idx_articles_category", "articles", ["category"])
    op.create_index(
        "idx_articles_importance", "articles", [sa.text("importance DESC")]
    )
    op.create_index("idx_articles_status", "articles", ["enrichment_status"])
    op.create_index("idx_articles_source", "articles", ["source"])
    op.execute(
        "CREATE INDEX idx_articles_embedding ON articles "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX idx_articles_fts ON articles USING gin("
        "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))"
        ")"
    )

    op.create_table(
        "preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "w_models",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "w_research",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "w_tools",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "w_cloud",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "w_industry",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "interest_terms",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "recency_weight",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0.7"),
            nullable=False,
        ),
        sa.Column(
            "streak_days",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "daily_digests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column(
            "top_articles",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("key_themes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "items_fetched",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_new",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "items_deduped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("ingestion_runs")
    op.drop_table("daily_digests")
    op.drop_table("preferences")
    op.drop_index("idx_articles_fts", table_name="articles")
    op.drop_index("idx_articles_embedding", table_name="articles")
    op.drop_index("idx_articles_source", table_name="articles")
    op.drop_index("idx_articles_status", table_name="articles")
    op.drop_index("idx_articles_importance", table_name="articles")
    op.drop_index("idx_articles_category", table_name="articles")
    op.drop_index("idx_articles_ingested_at", table_name="articles")
    op.drop_table("articles")

