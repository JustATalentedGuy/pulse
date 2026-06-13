import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.enrichment.quota_manager import get_quota_usage, reserve_quota
from app.main import app
from app.models.article import Article
from app.models.groq_quota import GroqQuotaUsage
from app.services.reembedding import reembed_articles
from app.services.retention import apply_retention
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "cloud-runtime-test"
TEST_EMBEDDING = [0.0] * 383 + [1.0]


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.fixture(autouse=True)
async def clean_cloud_runtime_data():
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()


async def test_cloud_job_requires_the_separate_job_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_settings = get_settings().model_copy(
        update={"job_secret": "cloud-job-secret"}  # pragma: allowlist secret
    )
    monkeypatch.setattr(
        "app.routers.jobs.get_settings",
        lambda: cloud_settings,
    )

    async with api_client() as client:
        forbidden = await client.post(
            "/jobs/heartbeat",
            headers={"X-API-Key": cloud_settings.api_key},
        )
        allowed = await client.post(
            "/jobs/heartbeat",
            headers={
                "X-Job-Secret": "cloud-job-secret"  # pragma: allowlist secret
            },
        )

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "awake"}


async def test_database_quota_reservation_is_atomic() -> None:
    cloud_settings = get_settings().model_copy(
        update={
            "groq_quota_backend": "database",
            "groq_daily_limit": 2,
        }
    )
    usage_date = datetime.now(
        ZoneInfo(cloud_settings.scheduler_timezone)
    ).date()
    async with SessionLocal() as session:
        existing = await session.get(GroqQuotaUsage, usage_date)
        previous_count = existing.request_count if existing else None
        await session.execute(
            delete(GroqQuotaUsage).where(
                GroqQuotaUsage.usage_date == usage_date
            )
        )
        await session.commit()

    try:
        results = await asyncio.gather(
            *(reserve_quota(settings=cloud_settings) for _ in range(4))
        )
        assert sum(results) == 2
        assert await get_quota_usage(settings=cloud_settings) == 2
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(GroqQuotaUsage).where(
                    GroqQuotaUsage.usage_date == usage_date
                )
            )
            if previous_count is not None:
                session.add(
                    GroqQuotaUsage(
                        usage_date=usage_date,
                        request_count=previous_count,
                    )
                )
            await session.commit()


async def test_reembedding_updates_model_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article_id = uuid.uuid4()
    title = f"Cloud vector migration {article_id}"
    url = f"https://example.invalid/cloud/{article_id}"
    async with SessionLocal() as session:
        session.add(
            Article(
                id=article_id,
                content_hash=compute_hash(title, url),
                title=title,
                url=url,
                source=TEST_SOURCE,
                raw_text="A detailed article about cloud vector migration.",
                summary="Cloud vector migration keeps semantic search consistent.",
                enrichment_status="done",
                embedding=[1.0] + [0.0] * 383,
                embedding_model="all-MiniLM-L6-v2",
            )
        )
        await session.commit()

    cloud_settings = get_settings().model_copy(
        update={"embedding_provider": "supabase"}
    )

    async def fake_embed(text: str) -> list[float]:
        return TEST_EMBEDDING

    monkeypatch.setattr(
        "app.services.reembedding.get_settings",
        lambda: cloud_settings,
    )
    monkeypatch.setattr(
        "app.services.reembedding.call_embedder",
        fake_embed,
    )

    result = await reembed_articles(
        batch_size=1,
        article_ids={article_id},
    )
    async with SessionLocal() as session:
        article = await session.get(Article, article_id)

    assert result.processed == 1
    assert article.embedding_model == "gte-small"
    assert list(article.embedding) == TEST_EMBEDDING


async def test_retention_clears_raw_html_and_old_skipped_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    recent_id = uuid.uuid4()
    skipped_id = uuid.uuid4()
    async with SessionLocal() as session:
        for article_id, status, ingested_at in (
            (recent_id, "done", now),
            (skipped_id, "skipped", now - timedelta(days=31)),
        ):
            title = f"Retention article {article_id}"
            url = f"https://example.invalid/retention/{article_id}"
            session.add(
                Article(
                    id=article_id,
                    content_hash=compute_hash(title, url),
                    title=title,
                    url=url,
                    source=TEST_SOURCE,
                    raw_text="Retention verification content.",
                    raw_html="<p>temporary</p>",
                    ingested_at=ingested_at,
                    enrichment_status=status,
                )
            )
        await session.commit()

    retention_settings = get_settings().model_copy(
        update={
            "article_retention_days": 180,
            "skipped_retention_days": 30,
            "ingestion_run_retention_days": 30,
        }
    )
    monkeypatch.setattr(
        "app.services.retention.get_settings",
        lambda: retention_settings,
    )

    result = await apply_retention(source=TEST_SOURCE)
    async with SessionLocal() as session:
        recent = await session.get(Article, recent_id)
        skipped = await session.get(Article, skipped_id)

    assert result.raw_html_cleared >= 1
    assert result.skipped_articles_deleted >= 1
    assert recent.raw_html is None
    assert skipped is None


def test_database_ssl_require_connect_args() -> None:
    settings = get_settings().model_copy(
        update={"database_ssl": True, "database_ssl_mode": "require"}
    )

    assert settings.database_connect_args == {"ssl": "require"}
