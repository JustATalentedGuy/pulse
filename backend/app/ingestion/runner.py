import argparse
import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.ingestion.arxiv import ArxivIngestor
from app.ingestion.base import BaseIngestor, RawItem
from app.ingestion.gmail import GmailIngestor
from app.ingestion.github_trending import GitHubTrendingIngestor
from app.ingestion.rss import RssIngestor
from app.models.article import Article
from app.models.ingestion_run import IngestionRun
from app.utils.date_parser import ensure_utc
from app.utils.hash import compute_hash, validate_url
from app.utils.text_cleaner import clean_body, clean_title


logger = logging.getLogger(__name__)


async def store_item(session: AsyncSession, item: RawItem) -> bool:
    title = clean_title(item.title)
    if not title:
        raise ValueError("Article title is empty after normalization")
    url = validate_url(item.url)
    raw_text = clean_body(item.raw_text)
    source = item.source.strip()[:100]
    if item.source_id:
        existing_id = await session.scalar(
            select(Article.id)
            .where(
                Article.source == source,
                Article.source_id == item.source_id,
            )
            .limit(1)
        )
        if existing_id is not None:
            return False
    stmt = (
        insert(Article)
        .values(
            content_hash=compute_hash(title, url),
            title=title,
            url=url,
            source=source,
            source_id=item.source_id,
            published_at=ensure_utc(item.published_at),
            raw_text=raw_text,
            raw_html=item.raw_html,
        )
        .on_conflict_do_nothing(index_elements=["content_hash"])
        .returning(Article.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one_or_none() is not None


async def run_ingestor(
    source_name: str,
    ingestor: BaseIngestor,
    session: AsyncSession,
) -> IngestionRun:
    run = IngestionRun(source=source_name, status="running")
    session.add(run)
    await session.commit()
    try:
        items = await ingestor.fetch()
        new_count = 0
        for item in items:
            if await store_item(session, item):
                new_count += 1
        run.status = "done"
        run.items_fetched = len(items)
        run.items_new = new_count
        run.items_deduped = len(items) - new_count
        run.completed_at = datetime.now(UTC)
    except Exception as exc:
        await session.rollback()
        run.status = "failed"
        run.error = str(exc)[:2000]
        run.completed_at = datetime.now(UTC)
        logger.exception("Ingestion failed for %s", source_name)
    session.add(run)
    await session.commit()
    return run


def build_ingestors(settings: Settings) -> dict[str, BaseIngestor]:
    return {
        "rss": RssIngestor(settings.rss_feed_entries),
        "github": GitHubTrendingIngestor(
            trending_url=settings.github_trending_url,
            search_url=settings.github_search_url,
            search_query=settings.github_search_query,
            user_agent=settings.github_user_agent,
        ),
        "arxiv": ArxivIngestor(
            api_url=settings.arxiv_api_url,
            categories=settings.arxiv_category_list,
            max_results=settings.arxiv_max_results,
        ),
        "gmail": GmailIngestor(
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            refresh_token=settings.gmail_refresh_token,
            newsletter_senders=settings.newsletter_sender_list,
        ),
    }


async def run_pipeline(
    sources: set[str] | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> list[IngestionRun]:
    ingestors = build_ingestors(get_settings())
    selected = {
        name: ingestor
        for name, ingestor in ingestors.items()
        if sources is None or name in sources
    }

    async def run_with_session(name: str, ingestor: BaseIngestor) -> IngestionRun:
        async with session_factory() as session:
            return await run_ingestor(name, ingestor, session)

    return await asyncio.gather(
        *(
            run_with_session(source_name, ingestor)
            for source_name, ingestor in selected.items()
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pulse ingestion sources")
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["rss", "github", "arxiv", "gmail"],
        help="Run only the selected sources",
    )
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    runs = asyncio.run(run_pipeline(set(args.sources) if args.sources else None))
    for run in runs:
        print(
            f"{run.source}: {run.status}; fetched={run.items_fetched}; "
            f"new={run.items_new}; deduped={run.items_deduped}"
        )


if __name__ == "__main__":
    main()
