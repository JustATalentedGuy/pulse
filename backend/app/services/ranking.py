from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.preference import Preference


CATEGORIES = ("models", "research", "tools", "cloud", "industry")


@dataclass(frozen=True)
class PreferenceProfile:
    weights: dict[str, float]
    interest_terms: tuple[str, ...]
    cold_start: bool


async def load_preference_profile(session: AsyncSession) -> PreferenceProfile:
    preference = await session.scalar(select(Preference).limit(1))
    if preference is None:
        weights = {category: 0.5 for category in CATEGORIES}
        return PreferenceProfile(weights=weights, interest_terms=(), cold_start=True)

    weights = {
        category: float(getattr(preference, f"w_{category}"))
        for category in CATEGORIES
    }
    interest_terms = tuple(preference.interest_terms or [])
    cold_start = (
        all(Decimal(str(weight)) == Decimal("0.5") for weight in weights.values())
        and not interest_terms
    )
    return PreferenceProfile(
        weights=weights,
        interest_terms=interest_terms,
        cold_start=cold_start,
    )


def personalized_score_expression(profile: PreferenceProfile):
    importance = func.coalesce(Article.importance, 3)
    if profile.cold_start:
        return importance * 2.0

    category_weight = case(
        *(
            (Article.category == category, weight)
            for category, weight in profile.weights.items()
        ),
        else_=0.5,
    )
    age_hours = (
        func.extract("epoch", func.now() - Article.ingested_at) / 3600.0
    )
    recency = func.greatest(
        0.0,
        func.least(5.0, 5.0 - age_hours / 6.0),
    )
    matches = [
        case((Article.keywords.any(term), 1), else_=0)
        for term in profile.interest_terms
    ]
    keyword_count = sum(matches, literal(0))
    keyword_bonus = func.least(keyword_count * 0.3, 1.5)
    return importance * 2.0 + category_weight * 3.0 + recency + keyword_bonus


def personalized_score(article: Article, profile: PreferenceProfile) -> float:
    importance = article.importance or 3
    if profile.cold_start:
        return float(importance * 2)

    category_weight = profile.weights.get(article.category or "", 0.5)
    hours_old = max(
        0.0,
        (datetime.now(UTC) - article.ingested_at).total_seconds() / 3600.0,
    )
    recency = max(0.0, 5.0 - hours_old / 6.0)
    overlap = set(article.keywords or []) & set(profile.interest_terms)
    keyword_bonus = min(len(overlap) * 0.3, 1.5)
    return (
        importance * 2.0
        + category_weight * 3.0
        + recency
        + keyword_bonus
    )
