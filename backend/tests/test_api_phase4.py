import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.preference import Preference
from app.routers.feed import background_tasks
from app.scheduler.jobs import scheduler
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase4-test"


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_key}


@pytest.fixture(autouse=True)
async def clean_phase4_articles():
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        preference = await session.scalar(select(Preference).limit(1))
        preference_snapshot = (
            {
                field: getattr(preference, field)
                for field in (
                    "w_models",
                    "w_research",
                    "w_tools",
                    "w_cloud",
                    "w_industry",
                    "interest_terms",
                    "streak_days",
                    "last_active_date",
                    "updated_at",
                )
            }
            if preference is not None
            else None
        )
        await session.commit()
    yield
    if background_tasks:
        await asyncio.gather(*background_tasks)
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        if preference_snapshot is not None:
            preference = await session.scalar(select(Preference).limit(1))
            if preference is not None:
                for field, value in preference_snapshot.items():
                    setattr(preference, field, value)
        await session.commit()


async def insert_articles(
    count: int,
    *,
    category: str = "models",
    title_prefix: str = "Phase 4",
    importance: int = 3,
) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        for index in range(count):
            article_id = uuid.uuid4()
            title = f"{title_prefix} {index} {article_id}"
            url = f"https://example.invalid/phase4/{article_id}"
            session.add(
                Article(
                    id=article_id,
                    content_hash=compute_hash(title, url),
                    title=title,
                    url=url,
                    source=TEST_SOURCE,
                    source_id=str(article_id),
                    published_at=now - timedelta(minutes=index),
                    ingested_at=now - timedelta(minutes=index),
                    raw_text=f"Test article body {index}",
                    summary=f"Summary for {title}",
                    category=category,
                    importance=importance,
                    entities={
                        "models": [],
                        "companies": [],
                        "techniques": [],
                        "datasets": [],
                    },
                    keywords=["phase4", category],
                    enrichment_status="done",
                )
            )
            ids.append(article_id)
        await session.commit()
    return ids


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


async def test_feed_pagination_returns_distinct_pages() -> None:
    ids = set(await insert_articles(20, importance=5))
    async with api_client() as client:
        first = await client.get(
            "/feed",
            params={"limit": 10, "offset": 0, "min_importance": 5},
            headers=auth_headers(),
        )
        second = await client.get(
            "/feed",
            params={"limit": 10, "offset": 10, "min_importance": 5},
            headers=auth_headers(),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    first_ids = {uuid.UUID(item["id"]) for item in first.json()["items"]} & ids
    second_ids = {uuid.UUID(item["id"]) for item in second.json()["items"]} & ids
    assert len(first_ids) == 10
    assert len(second_ids) == 10
    assert first_ids.isdisjoint(second_ids)
    assert first.json()["has_more"] is True


async def test_feed_category_filter() -> None:
    model_ids = set(await insert_articles(5, category="models", importance=5))
    await insert_articles(3, category="tools", importance=5)
    async with api_client() as client:
        response = await client.get(
            "/feed",
            params={"category": "models", "limit": 50, "min_importance": 5},
            headers=auth_headers(),
        )

    returned = {uuid.UUID(item["id"]) for item in response.json()["items"]}
    assert response.status_code == 200
    assert model_ids <= returned


async def test_api_key_is_required() -> None:
    async with api_client() as client:
        response = await client.get("/feed")
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid API key"}


async def test_read_event_is_recorded() -> None:
    article_id = (await insert_articles(1))[0]
    async with api_client() as client:
        response = await client.post(
            f"/feed/{article_id}/read",
            json={"duration_seconds": 45},
            headers=auth_headers(),
        )

    async with SessionLocal() as session:
        article = await session.get(Article, article_id)
    assert response.status_code == 200
    assert article is not None
    assert article.read_at is not None
    assert article.read_duration_s == 45


async def test_search_ranks_title_match_first() -> None:
    title_match = (await insert_articles(1, title_prefix="LangGraph orchestration"))[0]
    await insert_articles(1, title_prefix="Unrelated article")
    async with api_client() as client:
        response = await client.get(
            "/search",
            params={"q": "LangGraph", "mode": "fts"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == str(title_match)
    assert response.json()["mode"] == "fts"


def test_scheduler_registers_all_phase4_jobs() -> None:
    jobs = {job.id: str(job.trigger) for job in scheduler.get_jobs()}
    assert set(jobs) == {
        "ingest_all",
        "enrich_pending",
        "gmail_check",
        "daily_digest",
        "detect_trends",
        "weekly_summary",
    }
    assert "2:00:00" in jobs["ingest_all"]
    assert "0:30:00" in jobs["enrich_pending"]
    assert "4:00:00" in jobs["gmail_check"]
    assert "hour='7'" in jobs["daily_digest"]
    assert "hour='1'" in jobs["detect_trends"]
    assert "day_of_week='sun'" in jobs["weekly_summary"]
