import uuid
import json
from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.digest import DailyDigest
from app.services.digest import generate_daily_digest
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase5-test"
TEST_DIGEST_DATE = date(2099, 1, 1)
VALID_DIGEST = json.dumps(
    {
        "headline": "A focused day for practical AI engineering",
        "narrative": (
            "The leading development is a practical improvement in mobile AI "
            "engineering that gives teams a clearer route from prototypes to "
            "reliable products. Its importance comes from reducing the gap "
            "between model capability and a usable application experience.\n\n"
            "Across the strongest stories, the recurring themes are dependable "
            "tooling, careful evaluation, and production-minded design. These "
            "signals point toward a maturing ecosystem where implementation "
            "quality matters as much as raw model performance.\n\n"
            "Engineers should test the highlighted workflows against real user "
            "tasks this week, measure latency and failure modes, and keep the "
            "smallest useful feedback loop in place before scaling."
        ),
        "key_themes": ["mobile ai", "evaluation", "production tooling"],
    }
)


class DigestClient:
    async def complete(self, prompt: str) -> str:
        return VALID_DIGEST


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_key}


@pytest.fixture(autouse=True)
async def clean_phase5_data():
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(
            delete(DailyDigest).where(DailyDigest.date == TEST_DIGEST_DATE)
        )
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()


async def insert_article(
    *,
    bookmarked: bool = False,
    ingested_at: datetime | None = None,
) -> uuid.UUID:
    article_id = uuid.uuid4()
    title = f"Phase 5 article {article_id}"
    url = f"https://example.invalid/phase5/{article_id}"
    now = ingested_at or datetime.now(UTC)
    async with SessionLocal() as session:
        session.add(
            Article(
                id=article_id,
                content_hash=compute_hash(title, url),
                title=title,
                url=url,
                source=TEST_SOURCE,
                source_id=str(article_id),
                published_at=now,
                ingested_at=now,
                raw_text="A substantial Phase 5 article body for testing.",
                summary="A complete summary for the Phase 5 mobile experience.",
                category="tools",
                importance=5,
                entities={
                    "models": [],
                    "companies": [],
                    "techniques": ["mobile testing"],
                    "datasets": [],
                },
                keywords=["mobile", "testing", "pulse"],
                enrichment_status="done",
                bookmarked=bookmarked,
                bookmarked_at=now if bookmarked else None,
            )
        )
        await session.commit()
    return article_id


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


async def test_bookmark_persists_and_appears_in_bookmarks() -> None:
    article_id = await insert_article()
    async with api_client() as client:
        toggled = await client.post(
            f"/feed/{article_id}/bookmark",
            headers=auth_headers(),
        )
        bookmarks = await client.get("/bookmarks", headers=auth_headers())

    assert toggled.status_code == 200
    assert toggled.json() == {"bookmarked": True}
    assert bookmarks.status_code == 200
    assert str(article_id) in {item["id"] for item in bookmarks.json()["items"]}


async def test_hidden_article_does_not_return_after_refresh() -> None:
    article_id = await insert_article()
    async with api_client() as client:
        hidden = await client.post(
            f"/feed/{article_id}/hide",
            headers=auth_headers(),
        )
        feed = await client.get(
            "/feed",
            params={"limit": 50},
            headers=auth_headers(),
        )

    assert hidden.status_code == 200
    assert str(article_id) not in {item["id"] for item in feed.json()["items"]}


async def test_daily_digest_generation_is_idempotent_and_retrievable() -> None:
    article_id = await insert_article(
        ingested_at=datetime(2099, 1, 1, 8, tzinfo=UTC)
    )
    first = await generate_daily_digest(TEST_DIGEST_DATE, client=DigestClient())
    second = await generate_daily_digest(TEST_DIGEST_DATE, client=DigestClient())

    assert first is not None
    assert second is not None
    assert first.date == second.date

    async with SessionLocal() as session:
        digest_count = await session.scalar(
            select(func.count())
            .select_from(DailyDigest)
            .where(DailyDigest.date == first.date)
        )
    async with api_client() as client:
        response = await client.get(
            f"/digest/{TEST_DIGEST_DATE.isoformat()}",
            headers=auth_headers(),
        )

    assert digest_count == 1
    assert response.status_code == 200
    assert str(article_id) in {
        item["id"] for item in response.json()["top_articles"]
    }
    assert response.json()["headline"]
    assert response.json()["key_themes"]
