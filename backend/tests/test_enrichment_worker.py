import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.config import get_settings
from app.enrichment.quota_manager import QuotaManager
from app.enrichment.worker import enrich_pending
from app.models.article import Article
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase2-test"
TEST_EMBEDDING = [0.01] * 384
VALID_RESPONSE = json.dumps(
    {
        "summary": (
            "Claude 4 was adapted by Anthropic using LoRA. "
            "The result gives AI engineers a practical adaptation pattern."
        ),
        "category": "models",
        "importance": 4,
        "entities": {
            "models": ["Claude 4"],
            "companies": ["Anthropic"],
            "techniques": ["LoRA"],
            "datasets": [],
        },
        "keywords": [
            "claude 4",
            "anthropic",
            "lora",
            "model adaptation",
            "ai engineering",
        ],
    }
)


class RecordingClient:
    def __init__(self, failures: int = 0, delay: float = 0):
        self.failures = failures
        self.delay = delay
        self.calls = 0

    async def enrich(self, title: str, text: str) -> str:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.calls <= self.failures:
            raise ConnectionError("temporary connection failure")
        return VALID_RESPONSE


@pytest.fixture(autouse=True)
async def clean_test_articles():
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()


async def insert_articles(raw_texts: list[str]) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    async with SessionLocal() as session:
        for index, raw_text in enumerate(raw_texts):
            article_id = uuid.uuid4()
            title = f"Phase 2 test article {article_id}"
            url = f"https://example.invalid/phase2/{article_id}"
            session.add(
                Article(
                    id=article_id,
                    content_hash=compute_hash(title, url),
                    title=title,
                    url=url,
                    source=TEST_SOURCE,
                    source_id=str(index),
                    raw_text=raw_text,
                    ingested_at=datetime(2100, 1, 1, 0, index, tzinfo=UTC),
                    enrichment_status="pending",
                    enrichment_attempts=0,
                )
            )
            ids.append(article_id)
        await session.commit()
    return ids


def quota(tmp_path, limit: int = 100) -> QuotaManager:
    return QuotaManager(tmp_path / f"quota-{uuid.uuid4()}.json", limit)


async def load_articles(ids: list[uuid.UUID]) -> list[Article]:
    async with SessionLocal() as session:
        return list(
            (
                await session.scalars(
                    select(Article)
                    .where(Article.id.in_(ids))
                    .order_by(Article.source_id)
                )
            ).all()
        )


async def test_short_text_is_skipped_without_api_call(tmp_path) -> None:
    ids = await insert_articles(["AI is cool"])
    client = RecordingClient()

    result = await enrich_pending(
        batch_size=1,
        client=client,
        quota_manager=quota(tmp_path),
        embed_fn=lambda _: TEST_EMBEDDING,
        delay_seconds=0,
        article_ids=set(ids),
    )
    article = (await load_articles(ids))[0]

    assert result.skipped == 1
    assert article.enrichment_status == "skipped"
    assert client.calls == 0


async def test_quota_exhaustion_leaves_article_pending(tmp_path) -> None:
    ids = await insert_articles(["usable article text " * 10])
    client = RecordingClient()

    result = await enrich_pending(
        batch_size=1,
        client=client,
        quota_manager=quota(tmp_path, limit=0),
        embed_fn=lambda _: TEST_EMBEDDING,
        delay_seconds=0,
        article_ids=set(ids),
    )
    article = (await load_articles(ids))[0]

    assert result.quota_exhausted
    assert article.enrichment_status == "pending"
    assert client.calls == 0


async def test_missing_api_key_leaves_usable_article_pending(
    tmp_path,
    monkeypatch,
) -> None:
    ids = await insert_articles(["usable article text " * 10])
    settings_without_key = get_settings().model_copy(
        update={"groq_api_key": ""}
    )
    monkeypatch.setattr(
        "app.enrichment.worker.get_settings",
        lambda: settings_without_key,
    )

    result = await enrich_pending(
        batch_size=1,
        quota_manager=quota(tmp_path),
        embed_fn=lambda _: TEST_EMBEDDING,
        delay_seconds=0,
        article_ids=set(ids),
    )
    article = (await load_articles(ids))[0]

    assert result.processed == 0
    assert article.enrichment_status == "pending"
    assert article.enrichment_attempts == 0


async def test_retry_on_failure_records_two_attempts(tmp_path) -> None:
    ids = await insert_articles(["usable article text " * 10])
    client = RecordingClient(failures=1)

    result = await enrich_pending(
        batch_size=1,
        client=client,
        quota_manager=quota(tmp_path),
        embed_fn=lambda _: TEST_EMBEDDING,
        delay_seconds=0,
        article_ids=set(ids),
    )
    article = (await load_articles(ids))[0]

    assert result.done == 1
    assert client.calls == 2
    assert article.enrichment_attempts == 2
    assert article.enrichment_status == "done"


async def test_full_enrichment_round_trip_and_entity_format(tmp_path) -> None:
    ids = await insert_articles([f"usable article text {index} " * 10 for index in range(5)])
    client = RecordingClient()

    result = await enrich_pending(
        batch_size=5,
        client=client,
        quota_manager=quota(tmp_path),
        embed_fn=lambda _: TEST_EMBEDDING,
        delay_seconds=0,
        article_ids=set(ids),
    )
    articles = await load_articles(ids)

    assert result.done == 5
    assert client.calls == 5
    assert all(article.enrichment_status == "done" for article in articles)
    assert all(article.summary for article in articles)
    assert all(
        article.category
        in {"models", "research", "tools", "cloud", "industry", "other"}
        for article in articles
    )
    assert all(1 <= article.importance <= 5 for article in articles)
    assert all(len(article.embedding) == 384 for article in articles)
    assert all(article.entities["models"] == ["Claude 4"] for article in articles)
    assert all(article.entities["companies"] == ["Anthropic"] for article in articles)
    assert all(article.entities["techniques"] == ["LoRA"] for article in articles)
    assert all(
        all(value for values in article.entities.values() for value in values)
        for article in articles
    )


async def test_concurrent_workers_make_one_api_call(tmp_path) -> None:
    ids = await insert_articles(["usable article text " * 10])
    client = RecordingClient(delay=0.2)
    manager = quota(tmp_path)
    kwargs = {
        "batch_size": 1,
        "client": client,
        "quota_manager": manager,
        "embed_fn": lambda _: TEST_EMBEDDING,
        "delay_seconds": 0,
        "article_ids": set(ids),
    }

    results = await asyncio.gather(
        enrich_pending(**kwargs),
        enrich_pending(**kwargs),
    )
    article = (await load_articles(ids))[0]

    assert sum(result.done for result in results) == 1
    assert client.calls == 1
    assert article.enrichment_status == "done"
