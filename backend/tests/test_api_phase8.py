import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.enrichment.quota_manager import QuotaManager
from app.enrichment.worker import enrich_pending
from app.main import app
from app.models.article import Article
from app.models.trend import TrendingTopic
from app.models.user_settings import UserSettings
from app.services.ask import answer_question
from app.services.trends import detect_trends
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase8-test"
TEST_EMBEDDING = [1.0] + [0.0] * 383
WEATHER_EMBEDDING = [0.0, 1.0] + [0.0] * 382
IMPORTANCE_FIVE_RESPONSE = json.dumps(
    {
        "summary": (
            "A major model release improves production inference quality. "
            "The release matters for engineers deploying reliable AI systems."
        ),
        "category": "models",
        "importance": 5,
        "entities": {
            "models": ["Claude 4"],
            "companies": ["Anthropic"],
            "techniques": [],
            "datasets": [],
        },
        "keywords": [
            "claude 4",
            "anthropic",
            "inference",
            "production ai",
            "model release",
        ],
    }
)


class FakeAskClient:
    async def complete(self, prompt: str) -> str:
        return "LoRA adapts models with low-rank trainable matrices."


class FakeEnrichmentClient:
    async def enrich(self, title: str, text: str) -> str:
        return IMPORTANCE_FIVE_RESPONSE


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_key}


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.fixture(autouse=True)
async def clean_phase8_data():
    async with SessionLocal() as session:
        await session.execute(delete(TrendingTopic))
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        settings = await session.scalar(select(UserSettings).limit(1))
        token_snapshot = settings.expo_push_token if settings else None
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(delete(TrendingTopic))
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        settings = await session.scalar(select(UserSettings).limit(1))
        if settings is not None:
            settings.expo_push_token = token_snapshot
        await session.commit()


async def insert_article(
    *,
    title: str,
    entities: dict,
    ingested_at: datetime,
    embedding: list[float] | None = None,
    status: str = "done",
) -> uuid.UUID:
    article_id = uuid.uuid4()
    url = f"https://example.invalid/phase8/{article_id}"
    async with SessionLocal() as session:
        session.add(
            Article(
                id=article_id,
                content_hash=compute_hash(title, url),
                title=title,
                url=url,
                source=TEST_SOURCE,
                source_id=str(article_id),
                published_at=ingested_at,
                ingested_at=ingested_at,
                raw_text=(
                    "A detailed technical article with enough content for "
                    "enrichment and retrieval verification."
                ),
                summary=(
                    f"{title} explains low-rank adaptation for efficient "
                    "fine-tuning of large language models."
                    if status == "done"
                    else None
                ),
                category="models" if status == "done" else None,
                importance=4 if status == "done" else None,
                entities=entities if status == "done" else None,
                keywords=["lora", "fine-tuning"] if status == "done" else None,
                embedding=embedding,
                enrichment_status=status,
            )
        )
        await session.commit()
    return article_id


async def test_trend_detection_enforces_three_article_threshold() -> None:
    now = datetime(2095, 1, 2, 12, tzinfo=UTC)
    for index in range(2):
        await insert_article(
            title=f"Gemini article {index}",
            entities={
                "models": ["Gemini 2.0"],
                "companies": [],
                "techniques": [],
                "datasets": [],
            },
            ingested_at=now - timedelta(hours=index),
        )
    claude_ids = {
        await insert_article(
            title=f"Claude article {index}",
            entities={
                "models": ["Claude 4"],
                "companies": [],
                "techniques": [],
                "datasets": [],
            },
            ingested_at=now - timedelta(hours=index),
        )
        for index in range(4)
    }

    async with SessionLocal() as session:
        trends = await detect_trends(session, current_time=now)

    by_name = {trend.name: trend for trend in trends}
    assert "Claude 4" in by_name
    assert "Gemini 2.0" not in by_name
    assert by_name["Claude 4"].mention_count == 4
    assert set(by_name["Claude 4"].article_ids) == claude_ids


async def test_rag_answer_is_grounded_in_lora_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    lora_ids = {
        await insert_article(
            title=f"LoRA guide {index}",
            entities={
                "models": [],
                "companies": [],
                "techniques": ["LoRA"],
                "datasets": [],
            },
            ingested_at=now - timedelta(minutes=index),
            embedding=TEST_EMBEDDING,
        )
        for index in range(3)
    }

    def fake_embed(text: str) -> list[float]:
        return WEATHER_EMBEDDING if "weather" in text.lower() else TEST_EMBEDDING

    async def fake_answer(session, payload):
        return await answer_question(
            session,
            payload,
            client=FakeAskClient(),
            minimum_relevance=0.99,
        )

    monkeypatch.setattr("app.services.ask.embed", fake_embed)
    monkeypatch.setattr("app.routers.phase8.answer_question", fake_answer)
    async with api_client() as client:
        response = await client.post(
            "/ask",
            json={"question": "What is LoRA?", "conversation_history": []},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_groq"] is True
    assert {uuid.UUID(source["id"]) for source in payload["sources"]} == lora_ids
    assert "LoRA" in payload["answer"]


async def test_rag_returns_no_information_for_unrelated_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_embed(text: str) -> list[float]:
        return WEATHER_EMBEDDING

    async def fake_answer(session, payload):
        return await answer_question(
            session,
            payload,
            client=FakeAskClient(),
            minimum_relevance=0.99,
        )

    monkeypatch.setattr("app.services.ask.embed", fake_embed)
    monkeypatch.setattr("app.routers.phase8.answer_question", fake_answer)
    async with api_client() as client:
        response = await client.post(
            "/ask",
            json={
                "question": "What is the weather in Mumbai?",
                "conversation_history": [],
            },
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["used_groq"] is False
    assert response.json()["sources"] == []
    assert "do not have relevant information" in response.json()["answer"]


async def test_push_token_is_persisted() -> None:
    token = "ExponentPushToken[phase8-test-token]"
    async with api_client() as client:
        response = await client.post(
            "/user/push-token",
            json={"token": token},
            headers=auth_headers(),
        )

    async with SessionLocal() as session:
        stored = await session.scalar(
            select(UserSettings.expo_push_token).limit(1)
        )
    assert response.status_code == 200
    assert stored == token


async def test_importance_five_enrichment_triggers_notification(
    tmp_path,
) -> None:
    article_id = await insert_article(
        title="Importance five candidate",
        entities={},
        ingested_at=datetime.now(UTC),
        status="pending",
    )
    notifications: list[str] = []

    async def record_notification(session, article):
        notifications.append(article.title)

    result = await enrich_pending(
        batch_size=1,
        client=FakeEnrichmentClient(),
        quota_manager=QuotaManager(tmp_path / "quota.json", 10),
        embed_fn=lambda _: TEST_EMBEDDING,
        notification_fn=record_notification,
        delay_seconds=0,
        article_ids={article_id},
    )

    assert result.done == 1
    assert notifications == ["Importance five candidate"]
