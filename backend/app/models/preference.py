import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Date, DateTime, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    w_models: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.5")
    )
    w_research: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.5")
    )
    w_tools: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.5")
    )
    w_cloud: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.5")
    )
    w_industry: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("0.5")
    )
    interest_terms: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    recency_weight: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.7")
    )
    streak_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_active_date: Mapped[date | None] = mapped_column(Date)

