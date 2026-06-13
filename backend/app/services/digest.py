from datetime import UTC, date, datetime, time, timedelta
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.groq import GroqChatClient
from app.config import get_settings
from app.database import SessionLocal
from app.enrichment.parser import extract_json
from app.enrichment.quota_manager import QuotaManager, reserve_quota
from app.models.article import Article
from app.models.digest import DailyDigest
from app.schemas.digest import DigestGenerationResult
from app.services.notifications import notify_digest_ready


logger = logging.getLogger(__name__)


class DigestClient(Protocol):
    async def complete(self, prompt: str) -> str: ...


class DigestQuotaExhausted(RuntimeError):
    pass


def build_digest_prompt(articles: list[Article]) -> str:
    article_list = "\n".join(
        (
            f"- [{(article.category or 'other').upper()}] "
            f"{article.title}: {article.summary}"
        )
        for article in articles
    )
    return f"""You are writing a daily AI engineering intelligence digest.

Today's top articles:
{article_list}

Write a 3-paragraph digest:
1. Lead paragraph: the single most important development today and why it matters.
2. Trends paragraph: 2-3 themes you see emerging across multiple articles.
3. For engineers paragraph: what practitioners should pay attention to or try this week.

Also output a one-line headline for the digest and 3-5 key themes as a list.
The narrative must be between 200 and 5,000 characters.

Return ONLY JSON:
{{"headline": "...", "narrative": "...", "key_themes": ["...", "..."]}}"""


def _digest_window(
    target_date: date | None,
    timezone: ZoneInfo,
    current_time: datetime | None,
) -> tuple[date, datetime, datetime]:
    now = current_time or datetime.now(timezone)
    if target_date is None:
        digest_date = now.astimezone(timezone).date()
        window_end = now.astimezone(UTC)
    else:
        digest_date = target_date
        window_end = datetime.combine(
            digest_date + timedelta(days=1),
            time.min,
            tzinfo=UTC,
        )
    return digest_date, window_end - timedelta(hours=24), window_end


async def generate_daily_digest(
    target_date: date | None = None,
    *,
    client: DigestClient | None = None,
    quota_manager: QuotaManager | None = None,
    current_time: datetime | None = None,
    notification_fn: Callable[
        [AsyncSession, DailyDigest],
        Awaitable[None],
    ] = notify_digest_ready,
) -> DailyDigest | None:
    settings = get_settings()
    timezone = ZoneInfo(settings.scheduler_timezone)
    digest_date, cutoff, window_end = _digest_window(
        target_date,
        timezone,
        current_time,
    )

    async with SessionLocal() as session:
        existing = await session.scalar(
            select(DailyDigest).where(DailyDigest.date == digest_date)
        )
        if existing is not None:
            return existing

        articles = list(
            (
                await session.scalars(
                    select(Article)
                    .where(
                        Article.enrichment_status == "done",
                        Article.hidden.is_(False),
                        Article.ingested_at >= cutoff,
                        Article.ingested_at < window_end,
                    )
                    .order_by(
                        Article.importance.desc().nullslast(),
                        Article.ingested_at.desc(),
                    )
                    .limit(10)
                )
            ).all()
        )
        if not articles:
            return None

        digest_client = client
        if digest_client is None:
            if not await reserve_quota(quota_manager, settings):
                raise DigestQuotaExhausted
            digest_client = GroqChatClient(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
            )
        elif quota_manager is not None and not await reserve_quota(
            quota_manager,
            settings,
        ):
            raise DigestQuotaExhausted

        response = await digest_client.complete(build_digest_prompt(articles))
        result = DigestGenerationResult.model_validate(extract_json(response))
        values = {
            "date": digest_date,
            "generated_at": datetime.now(UTC),
            "headline": result.headline,
            "top_articles": [article.id for article in articles],
            "narrative": result.narrative,
            "key_themes": result.key_themes,
        }
        statement = (
            insert(DailyDigest)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[DailyDigest.date])
            .returning(DailyDigest)
        )
        digest = (await session.execute(statement)).scalar_one_or_none()
        created = digest is not None
        if digest is None:
            digest = await session.scalar(
                select(DailyDigest).where(DailyDigest.date == digest_date)
            )
        await session.commit()
        if created:
            try:
                await notification_fn(session, digest)
            except Exception:
                logger.exception(
                    "Digest notification failed for %s",
                    digest.date,
                )
        return digest
