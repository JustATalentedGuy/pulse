import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Awaitable
from typing import Callable, Protocol
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.enrichment.embedder import call_embedder
from app.enrichment.groq_client import GroqEnrichmentClient
from app.enrichment.parser import parse_enrichment
from app.enrichment.quota_manager import (
    QuotaManager,
    quota_is_available,
    reserve_quota,
)
from app.models.article import Article
from app.schemas.enrichment import EnrichmentResult
from app.services.notifications import notify_importance_article
from app.utils.text_cleaner import clean_llm_text


logger = logging.getLogger(__name__)
MINIMUM_TEXT_LENGTH = 50
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 3000
MAX_ATTEMPTS = 3


class EnrichmentClient(Protocol):
    async def enrich(self, title: str, text: str) -> str: ...


class DailyQuotaExhausted(RuntimeError):
    pass


@dataclass(slots=True)
class WorkerResult:
    processed: int = 0
    done: int = 0
    failed: int = 0
    skipped: int = 0
    quota_exhausted: bool = False


def prepare_article_input(article: Article) -> tuple[str, str]:
    title = clean_llm_text(article.title, MAX_TITLE_LENGTH)
    body = clean_llm_text(article.raw_text, MAX_TEXT_LENGTH)
    return title, body


def build_quota_manager(settings: Settings) -> QuotaManager:
    path = Path(settings.groq_quota_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return QuotaManager(path=path, daily_limit=settings.groq_daily_limit)


async def _claim_next_article(
    session: AsyncSession,
    article_ids: set[UUID] | None = None,
) -> Article | None:
    async with session.begin():
        conditions = [
            Article.enrichment_status == "pending",
            Article.enrichment_attempts < MAX_ATTEMPTS,
        ]
        if article_ids is not None:
            conditions.append(Article.id.in_(article_ids))
        article = await session.scalar(
            select(Article)
            .where(*conditions)
            .order_by(Article.ingested_at.desc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if article is None:
            return None

        _, body = prepare_article_input(article)
        if len(body) < MINIMUM_TEXT_LENGTH:
            article.enrichment_status = "skipped"
            article.enrichment_error = (
                f"Usable text is shorter than {MINIMUM_TEXT_LENGTH} characters"
            )
            return article

        article.enrichment_status = "processing"
        article.enrichment_error = None
        return article


async def _skip_short_articles(
    session: AsyncSession,
    article_ids: set[UUID] | None = None,
) -> int:
    conditions = [
        Article.enrichment_status == "pending",
        Article.enrichment_attempts < MAX_ATTEMPTS,
        func.length(func.trim(func.coalesce(Article.raw_text, "")))
        < MINIMUM_TEXT_LENGTH,
    ]
    if article_ids is not None:
        conditions.append(Article.id.in_(article_ids))
    result = await session.execute(
        update(Article)
        .where(*conditions)
        .values(
            enrichment_status="skipped",
            enrichment_error=(
                f"Usable text is shorter than {MINIMUM_TEXT_LENGTH} characters"
            ),
        )
    )
    await session.commit()
    return result.rowcount


async def _save_success(
    session: AsyncSession,
    article: Article,
    result: EnrichmentResult,
    embedding: list[float],
    notification_fn: Callable[
        [AsyncSession, Article],
        Awaitable[None],
    ],
) -> None:
    article.summary = result.summary
    article.category = result.category
    article.importance = result.importance
    article.entities = result.entities.model_dump()
    article.keywords = result.keywords
    article.embedding = embedding
    article.embedding_model = get_settings().embedding_model_name
    article.enrichment_status = "done"
    article.enrichment_error = None
    article.enriched_at = datetime.now(UTC)
    await session.commit()
    try:
        await notification_fn(session, article)
    except Exception:
        logger.exception(
            "Importance notification failed for article %s",
            article.id,
        )


async def _release_for_quota(session: AsyncSession, article: Article) -> None:
    article.enrichment_status = "pending"
    article.enrichment_error = None
    await session.commit()


async def enrich_article(
    session: AsyncSession,
    article: Article,
    client: EnrichmentClient,
    quota_manager: QuotaManager | None,
    embed_fn: Callable[
        [str],
        list[float] | Awaitable[list[float]],
    ]
    | None = None,
    notification_fn: Callable[
        [AsyncSession, Article],
        Awaitable[None],
    ] = notify_importance_article,
) -> str:
    title, body = prepare_article_input(article)
    remaining_attempts = MAX_ATTEMPTS - article.enrichment_attempts
    if remaining_attempts <= 0:
        article.enrichment_status = "failed"
        article.enrichment_error = "Maximum enrichment attempts reached"
        await session.commit()
        return "failed"

    retrying = AsyncRetrying(
        stop=stop_after_attempt(remaining_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_not_exception_type(DailyQuotaExhausted),
        reraise=True,
    )
    try:
        async for attempt in retrying:
            with attempt:
                if not await reserve_quota(quota_manager):
                    raise DailyQuotaExhausted
                article.enrichment_attempts += 1
                await session.commit()

                raw_result = await client.enrich(title=title, text=body)
                result = parse_enrichment(raw_result)
                if result.summary.casefold().strip() == title.casefold().strip():
                    raise ValueError("Enrichment summary duplicates the article title")
    except DailyQuotaExhausted:
        await _release_for_quota(session, article)
        return "quota_exhausted"
    except Exception as exc:
        article.enrichment_status = (
            "failed"
            if article.enrichment_attempts >= MAX_ATTEMPTS
            else "pending"
        )
        article.enrichment_error = str(exc)[:2000]
        await session.commit()
        logger.error("Enrichment failed for article %s: %s", article.id, exc)
        return article.enrichment_status

    try:
        vector = await call_embedder(result.summary, embed_fn)
        await _save_success(
            session,
            article,
            result,
            vector,
            notification_fn,
        )
    except Exception as exc:
        article.enrichment_status = "failed"
        article.enrichment_error = f"Embedding failed: {exc}"[:2000]
        await session.commit()
        logger.exception("Embedding failed for article %s", article.id)
        return "failed"
    return "done"


async def enrich_pending(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    *,
    batch_size: int = 20,
    client: EnrichmentClient | None = None,
    quota_manager: QuotaManager | None = None,
    embed_fn: Callable[
        [str],
        list[float] | Awaitable[list[float]],
    ]
    | None = None,
    notification_fn: Callable[
        [AsyncSession, Article],
        Awaitable[None],
    ] = notify_importance_article,
    delay_seconds: float | None = None,
    article_ids: set[UUID] | None = None,
) -> WorkerResult:
    settings = get_settings()
    result = WorkerResult()
    quota = quota_manager
    if quota is None and settings.groq_quota_backend != "database":
        quota = build_quota_manager(settings)
    async with session_factory() as session:
        skipped = await _skip_short_articles(session, article_ids=article_ids)
    result.processed += skipped
    result.skipped += skipped

    if not await quota_is_available(quota, settings):
        logger.warning("Groq quota exhausted for today. Skipping enrichment.")
        result.quota_exhausted = True
        return result
    if client is None and not settings.groq_api_key:
        logger.warning(
            "GROQ_API_KEY is not configured. Usable articles remain pending."
        )
        return result

    enrichment_client = client
    delay = (
        settings.groq_request_delay_seconds
        if delay_seconds is None
        else delay_seconds
    )

    for index in range(batch_size):
        async with session_factory() as session:
            article = await _claim_next_article(session, article_ids=article_ids)
            if article is None:
                break
            if article.enrichment_status == "skipped":
                result.processed += 1
                result.skipped += 1
                continue
            if enrichment_client is None:
                enrichment_client = GroqEnrichmentClient(
                    api_key=settings.groq_api_key,
                    model=settings.groq_model,
                )

            outcome = await enrich_article(
                session=session,
                article=article,
                client=enrichment_client,
                quota_manager=quota,
                embed_fn=embed_fn,
                notification_fn=notification_fn,
            )
            result.processed += 1
            if outcome == "done":
                result.done += 1
            elif outcome == "failed":
                result.failed += 1
            elif outcome == "quota_exhausted":
                result.quota_exhausted = True
                break

        if delay > 0 and index < batch_size - 1:
            await asyncio.sleep(delay)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich pending Pulse articles")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    result = asyncio.run(enrich_pending(batch_size=args.batch_size))
    print(
        f"processed={result.processed}; done={result.done}; "
        f"failed={result.failed}; skipped={result.skipped}; "
        f"quota_exhausted={result.quota_exhausted}"
    )


if __name__ == "__main__":
    main()
