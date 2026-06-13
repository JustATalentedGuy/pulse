import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.preference import Preference
from app.services.preferences import update_preferences
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase6-test"
PREFERENCE_FIELDS = (
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


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_key}


def fake_embed(text: str) -> list[float]:
    normalized = text.lower()
    vector = [0.0] * 384
    if any(term in normalized for term in ("attention", "transformer", "multi-head")):
        vector[0] = 1.0
    elif any(term in normalized for term in ("cloud", "cost optimisation", "kubernetes")):
        vector[1] = 1.0
    elif any(term in normalized for term in ("gpt", "language model", "internals")):
        vector[2] = 1.0
    else:
        vector[3] = 1.0
    return vector


@pytest.fixture(autouse=True)
async def clean_phase6_data():
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        preference = await session.scalar(select(Preference).limit(1))
        snapshot = {
            field: getattr(preference, field)
            for field in PREFERENCE_FIELDS
        }
        preference.w_models = Decimal("0.500")
        preference.w_research = Decimal("0.500")
        preference.w_tools = Decimal("0.500")
        preference.w_cloud = Decimal("0.500")
        preference.w_industry = Decimal("0.500")
        preference.interest_terms = []
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        preference = await session.scalar(select(Preference).limit(1))
        for field, value in snapshot.items():
            setattr(preference, field, value)
        await session.commit()


async def insert_article(
    *,
    title: str,
    summary: str,
    category: str = "models",
    importance: int = 3,
    keywords: list[str] | None = None,
    ingested_at: datetime | None = None,
) -> uuid.UUID:
    article_id = uuid.uuid4()
    url = f"https://example.invalid/phase6/{article_id}"
    timestamp = ingested_at or datetime.now(UTC)
    async with SessionLocal() as session:
        session.add(
            Article(
                id=article_id,
                content_hash=compute_hash(title, url),
                title=title,
                url=url,
                source=TEST_SOURCE,
                source_id=str(article_id),
                published_at=timestamp,
                ingested_at=timestamp,
                raw_text=summary,
                summary=summary,
                category=category,
                importance=importance,
                entities={
                    "models": [],
                    "companies": [],
                    "techniques": [],
                    "datasets": [],
                },
                keywords=keywords or [],
                embedding=fake_embed(f"{title} {summary}"),
                enrichment_status="done",
            )
        )
        await session.commit()
    return article_id


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


async def set_preferences(
    *,
    models: str = "0.500",
    research: str = "0.500",
    tools: str = "0.500",
    cloud: str = "0.500",
    industry: str = "0.500",
    interest_terms: list[str] | None = None,
) -> None:
    async with SessionLocal() as session:
        preference = await session.scalar(select(Preference).limit(1))
        preference.w_models = Decimal(models)
        preference.w_research = Decimal(research)
        preference.w_tools = Decimal(tools)
        preference.w_cloud = Decimal(cloud)
        preference.w_industry = Decimal(industry)
        preference.interest_terms = interest_terms or []
        await session.commit()


async def test_semantic_search_returns_transformer_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.routers.search.embed", fake_embed)
    transformer_ids = {
        await insert_article(
            title=f"Transformer architecture study {index}",
            summary="Multi-head attention mechanisms and token representations.",
        )
        for index in range(5)
    }
    for index in range(5):
        await insert_article(
            title=f"Cloud finance guide {index}",
            summary="Kubernetes cloud cost optimisation and budget controls.",
            category="cloud",
        )

    async with api_client() as client:
        response = await client.get(
            "/search",
            params={"q": "multi-head attention", "mode": "semantic", "limit": 5},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "semantic"
    returned = {uuid.UUID(item["id"]) for item in response.json()["results"]}
    assert returned == transformer_ids


async def test_semantic_and_hybrid_find_concept_without_exact_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.routers.search.embed", fake_embed)
    concept_ids = {
        await insert_article(
            title=f"Language model internals {index}",
            summary="Token prediction layers and autoregressive neural architecture.",
        )
        for index in range(2)
    }

    async with api_client() as client:
        fts = await client.get(
            "/search",
            params={"q": "how GPT works", "mode": "fts", "limit": 10},
            headers=auth_headers(),
        )
        semantic = await client.get(
            "/search",
            params={"q": "how GPT works", "mode": "semantic", "limit": 10},
            headers=auth_headers(),
        )
        hybrid = await client.get(
            "/search",
            params={"q": "how GPT works", "mode": "hybrid", "limit": 10},
            headers=auth_headers(),
        )

    fts_ids = {uuid.UUID(item["id"]) for item in fts.json()["results"]}
    semantic_ids = {uuid.UUID(item["id"]) for item in semantic.json()["results"]}
    hybrid_ids = {uuid.UUID(item["id"]) for item in hybrid.json()["results"]}
    assert not concept_ids & fts_ids
    assert concept_ids <= semantic_ids
    assert concept_ids <= hybrid_ids


async def test_strong_read_updates_category_and_keywords() -> None:
    article_id = await insert_article(
        title="A model systems article",
        summary="A detailed model serving design.",
        keywords=["inference", "serving", "latency", "ignored"],
    )
    async with SessionLocal() as session:
        article = await session.get(Article, article_id)
        await update_preferences(session, article, 180)
        preference = await session.scalar(select(Preference).limit(1))

    assert Decimal(preference.w_models) > Decimal("0.500")
    assert Decimal(preference.w_models) <= Decimal("1.000")
    assert preference.interest_terms == ["inference", "serving", "latency"]


async def test_only_read_category_weight_changes() -> None:
    article_id = await insert_article(
        title="Developer tooling",
        summary="A productive tool chain for engineers.",
        category="tools",
    )
    async with SessionLocal() as session:
        article = await session.get(Article, article_id)
        for _ in range(20):
            await update_preferences(session, article, 180)
        preference = await session.scalar(select(Preference).limit(1))

    assert preference.w_tools > preference.w_research
    assert preference.w_research == Decimal("0.500")


async def test_personalized_feed_ranks_preferred_category_first() -> None:
    now = datetime.now(UTC)
    model_id = await insert_article(
        title="Preferred model article",
        summary="Model engineering.",
        category="models",
        ingested_at=now,
    )
    tool_id = await insert_article(
        title="Less preferred tool article",
        summary="Developer tools.",
        category="tools",
        ingested_at=now,
    )
    await set_preferences(models="0.900", tools="0.200")

    async with api_client() as client:
        response = await client.get(
            "/feed",
            params={
                "limit": 10,
                "since": (now - timedelta(seconds=1)).isoformat(),
            },
            headers=auth_headers(),
        )

    ids = [uuid.UUID(item["id"]) for item in response.json()["items"]]
    assert ids.index(model_id) < ids.index(tool_id)


async def test_interest_term_overlap_adds_feed_bonus() -> None:
    now = datetime.now(UTC)
    matching_id = await insert_article(
        title="Matching keyword article",
        summary="An article about inference systems.",
        keywords=["inference"],
        ingested_at=now,
    )
    other_id = await insert_article(
        title="Non-matching keyword article",
        summary="An article about unrelated systems.",
        keywords=["unrelated"],
        ingested_at=now,
    )
    await set_preferences(models="0.600", interest_terms=["inference"])

    async with api_client() as client:
        response = await client.get(
            "/feed",
            params={
                "limit": 10,
                "since": (now - timedelta(seconds=1)).isoformat(),
            },
            headers=auth_headers(),
        )

    ids = [uuid.UUID(item["id"]) for item in response.json()["items"]]
    assert ids.index(matching_id) < ids.index(other_id)


async def test_cold_start_orders_by_importance_then_ingested_at() -> None:
    now = datetime.now(UTC)
    high_id = await insert_article(
        title="High importance",
        summary="Older but more important.",
        importance=4,
        ingested_at=now - timedelta(seconds=2),
    )
    newer_id = await insert_article(
        title="Newest equal importance",
        summary="Newest among equal importance.",
        importance=3,
        ingested_at=now,
    )
    older_id = await insert_article(
        title="Older equal importance",
        summary="Older among equal importance.",
        importance=3,
        ingested_at=now - timedelta(seconds=1),
    )
    await set_preferences()

    async with api_client() as client:
        response = await client.get(
            "/feed",
            params={
                "limit": 10,
                "since": (now - timedelta(seconds=3)).isoformat(),
            },
            headers=auth_headers(),
        )

    ids = [uuid.UUID(item["id"]) for item in response.json()["items"]]
    assert ids[:3] == [high_id, newer_id, older_id]
