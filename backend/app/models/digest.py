import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    headline: Mapped[str | None] = mapped_column(Text)
    top_articles: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True))
    )
    narrative: Mapped[str | None] = mapped_column(Text)
    key_themes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

