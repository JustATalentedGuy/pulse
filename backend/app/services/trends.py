from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.trend import TrendingTopic


TREND_THRESHOLD = 3


async def detect_trends(
    session: AsyncSession,
    *,
    current_time: datetime | None = None,
    threshold: int = TREND_THRESHOLD,
) -> list[TrendingTopic]:
    now = current_time or datetime.now(UTC)
    cutoff = now - timedelta(hours=48)
    rows = (
        await session.execute(
            select(Article.id, Article.entities).where(
                Article.enrichment_status == "done",
                Article.ingested_at >= cutoff,
                Article.entities.is_not(None),
            )
        )
    ).all()

    counts: Counter[str] = Counter()
    article_ids: dict[str, list] = defaultdict(list)
    display_names: dict[str, str] = {}
    for article_id, entity_map in rows:
        article_entities: dict[str, str] = {}
        for names in (entity_map or {}).values():
            if not isinstance(names, list):
                continue
            for name in names:
                if not isinstance(name, str):
                    continue
                cleaned = " ".join(name.split()).strip()
                normalized = cleaned.casefold()
                if cleaned and normalized not in article_entities:
                    article_entities[normalized] = cleaned
        for normalized, display_name in article_entities.items():
            counts[normalized] += 1
            article_ids[normalized].append(article_id)
            display_names.setdefault(normalized, display_name)

    await session.execute(delete(TrendingTopic))
    trends = [
        TrendingTopic(
            name=display_names[name],
            mention_count=count,
            article_ids=article_ids[name],
            detected_at=now,
        )
        for name, count in counts.most_common()
        if count >= threshold
    ]
    session.add_all(trends)
    await session.commit()
    return trends
