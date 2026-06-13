from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.article import Article
from app.models.preference import Preference


SUPPORTED_CATEGORIES = {"models", "research", "tools", "cloud", "industry"}
ALPHA = Decimal("0.1")


async def ensure_preference_row() -> None:
    async with SessionLocal() as session:
        preference = await session.scalar(select(Preference).limit(1))
        if preference is None:
            session.add(Preference())
            await session.commit()


def engagement_signal(duration_seconds: int) -> Decimal | None:
    if duration_seconds < 5:
        return None
    if duration_seconds < 30:
        return Decimal("0.2")
    if duration_seconds < 120:
        return Decimal("0.5")
    return Decimal("1.0")


async def update_preferences(
    session: AsyncSession,
    article: Article,
    duration_seconds: int,
) -> None:
    signal = engagement_signal(duration_seconds)
    if signal is None:
        return

    preference = await session.scalar(
        select(Preference).with_for_update().limit(1)
    )
    if preference is None:
        preference = Preference()
        session.add(preference)
        await session.flush()

    if article.category in SUPPORTED_CATEGORIES:
        field = f"w_{article.category}"
        current = Decimal(getattr(preference, field))
        updated = current * (Decimal("1.0") - ALPHA) + signal * ALPHA
        updated = min(Decimal("1.000"), max(Decimal("0.000"), updated))
        setattr(
            preference,
            field,
            updated.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
        )

    interest_terms = list(preference.interest_terms or [])
    seen = set(interest_terms)
    for keyword in (article.keywords or [])[:3]:
        normalized = keyword.strip().lower()
        if normalized and normalized not in seen:
            interest_terms.append(normalized)
            seen.add(normalized)
    preference.interest_terms = interest_terms[:50]

    today = date.today()
    if preference.last_active_date == today - timedelta(days=1):
        preference.streak_days += 1
    elif preference.last_active_date != today:
        preference.streak_days = 1
    preference.last_active_date = today
    preference.updated_at = datetime.now(UTC)
    await session.commit()


async def update_preference_after_read(
    article_id: UUID,
    duration_seconds: int,
) -> None:
    async with SessionLocal() as session:
        article = await session.get(Article, article_id)
        if article is None:
            return
        await update_preferences(session, article, duration_seconds)
