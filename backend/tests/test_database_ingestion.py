import asyncio
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.ingestion.base import BaseIngestor, RawItem
from app.ingestion.runner import run_ingestor, run_pipeline, store_item
from app.models.article import Article
from app.models.ingestion_run import IngestionRun
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration


class DuplicateIngestor(BaseIngestor):
    def __init__(self, item: RawItem):
        self.item = item

    async def fetch(self) -> list[RawItem]:
        return [self.item, self.item]


class FailingIngestor(BaseIngestor):
    async def fetch(self) -> list[RawItem]:
        raise ConnectionError("mock Gmail connection failure")


def make_item(
    *,
    title: str | None = None,
    raw_text: str = "database test body",
) -> RawItem:
    unique = uuid.uuid4().hex
    base_url = (
        get_test_base_url().rstrip("/")
        + "/"
        + unique
    )
    return RawItem(
        title=title or f"Database test {unique}",
        url=base_url,
        source="test",
        source_id=unique,
        published_at=None,
        raw_text=raw_text,
        raw_html=None,
    )


def get_test_base_url() -> str:
    from app.config import get_settings

    return get_settings().rss_feed_entries[0].split("|", 1)[-1].split("?", 1)[0]


async def delete_article(item: RawItem) -> None:
    async with SessionLocal() as session:
        await session.execute(
            delete(Article).where(
                Article.content_hash == compute_hash(item.title, item.url)
            )
        )
        await session.commit()


async def test_hash_deduplication_and_run_record() -> None:
    item = make_item()
    async with SessionLocal() as session:
        run = await run_ingestor(
            f"test-{uuid.uuid4().hex}",
            DuplicateIngestor(item),
            session,
        )
        count = await session.scalar(
            select(func.count())
            .select_from(Article)
            .where(Article.content_hash == compute_hash(item.title, item.url))
        )

    assert count == 1
    assert run.items_fetched == 2
    assert run.items_new == 1
    assert run.items_deduped == 1
    async with SessionLocal() as session:
        await session.execute(delete(IngestionRun).where(IngestionRun.id == run.id))
        await session.commit()
    await delete_article(item)


async def test_missing_date_is_stored_as_null() -> None:
    item = make_item()
    async with SessionLocal() as session:
        assert await store_item(session, item)
        published_at = await session.scalar(
            select(Article.published_at).where(
                Article.content_hash == compute_hash(item.title, item.url)
            )
        )

    assert published_at is None
    await delete_article(item)


async def test_text_is_capped_at_8000_characters() -> None:
    item = make_item(raw_text="x" * 10_000)
    async with SessionLocal() as session:
        assert await store_item(session, item)
        stored_length = await session.scalar(
            select(func.length(Article.raw_text)).where(
                Article.content_hash == compute_hash(item.title, item.url)
            )
        )

    assert stored_length == 8000
    await delete_article(item)


async def test_concurrent_inserts_create_one_row() -> None:
    item = make_item()

    async def insert_once() -> bool:
        async with SessionLocal() as session:
            return await store_item(session, item)

    inserted = await asyncio.gather(*(insert_once() for _ in range(5)))
    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Article)
            .where(Article.content_hash == compute_hash(item.title, item.url))
        )

    assert sum(inserted) == 1
    assert count == 1
    await delete_article(item)


async def test_source_id_prevents_duplicate_message_insert() -> None:
    item = make_item()
    item.source = "gmail"
    changed_item = RawItem(
        title=f"{item.title} changed",
        url=f"{item.url}/changed",
        source=item.source,
        source_id=item.source_id,
        published_at=None,
        raw_text=item.raw_text,
        raw_html=None,
    )

    async with SessionLocal() as session:
        assert await store_item(session, item)
        assert not await store_item(session, changed_item)
        count = await session.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.source == item.source,
                Article.source_id == item.source_id,
            )
        )

    assert count == 1
    await delete_article(item)


async def test_gmail_failure_does_not_stop_other_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rss_item = make_item()
    hackernews_item = make_item()
    rss_item.source = "rss-test"
    hackernews_item.source = "hackernews-test"

    monkeypatch.setattr(
        "app.ingestion.runner.build_ingestors",
        lambda settings: {
            "rss": DuplicateIngestor(rss_item),
            "hackernews": DuplicateIngestor(hackernews_item),
            "gmail": FailingIngestor(),
        },
    )

    runs = await run_pipeline(session_factory=SessionLocal)
    by_source = {run.source: run for run in runs}

    assert by_source["rss"].status == "done"
    assert by_source["hackernews"].status == "done"
    assert by_source["gmail"].status == "failed"
    assert "mock Gmail connection failure" in (by_source["gmail"].error or "")

    async with SessionLocal() as session:
        await session.execute(
            delete(IngestionRun).where(
                IngestionRun.id.in_([run.id for run in runs])
            )
        )
        await session.commit()
    await delete_article(rss_item)
    await delete_article(hackernews_item)
