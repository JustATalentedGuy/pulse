import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        Index(
            "idx_articles_ingested_at",
            text("ingested_at DESC"),
            postgresql_using="btree",
        ),
        Index("idx_articles_category", "category"),
        Index("idx_articles_importance", text("importance DESC")),
        Index("idx_articles_status", "enrichment_status"),
        Index("idx_articles_source", "source"),
        Index("idx_articles_embedding_model", "embedding_model"),
        Index(
            "idx_articles_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
        Index(
            "idx_articles_fts",
            text(
                "to_tsvector('english'::regconfig, "
                "(COALESCE(title, ''::text) || ' '::text) "
                "|| COALESCE(summary, ''::text))"
            ),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_html: Mapped[str | None] = mapped_column(Text)

    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50))
    importance: Mapped[int | None] = mapped_column(SmallInteger)
    entities: Mapped[dict | None] = mapped_column(JSONB)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default=text("'all-MiniLM-L6-v2'"),
    )

    enrichment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    enrichment_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    enrichment_error: Mapped[str | None] = mapped_column(Text)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_duration_s: Mapped[int | None] = mapped_column(Integer)
    bookmarked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    bookmarked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quiz_attempted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    quiz_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
