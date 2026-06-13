import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.digest import DailyDigest
from app.models.quiz import QuizAttempt
from app.services.digest import generate_daily_digest
from app.services.quiz import create_quiz, quiz_sessions
from app.schemas.digest import DigestGenerationResult
from app.utils.hash import compute_hash


pytestmark = pytest.mark.integration
TEST_SOURCE = "phase7-test"
DIGEST_DATE = date(2097, 7, 7)
EMPTY_DIGEST_DATE = date(2097, 7, 8)
QUIZ_RESPONSE = json.dumps(
    [
        {
            "question": "Why does normalized embedding storage help semantic search?",
            "options": {
                "A": "It removes the need for a database",
                "B": "It makes cosine comparisons consistent",
                "C": "It converts every query into SQL text",
                "D": "It guarantees every result is relevant",
            },
            "correct": "B",
            "explanation": "Normalization makes cosine-based similarity comparable across vectors.",
        },
        {
            "question": "What is the main role of reciprocal rank fusion?",
            "options": {
                "A": "Merge rankings without requiring equal score scales",
                "B": "Generate article summaries",
                "C": "Replace vector embeddings",
                "D": "Delete duplicate source records",
            },
            "correct": "A",
            "explanation": "RRF combines ranked lists using their positions rather than raw scores.",
        },
        {
            "question": "Why should preference updates use bounded weights?",
            "options": {
                "A": "To prevent all articles from being enriched",
                "B": "To force every category to rank equally",
                "C": "To keep repeated engagement from producing unstable scores",
                "D": "To avoid storing read duration",
            },
            "correct": "C",
            "explanation": "Clamping keeps repeated signals from pushing ranking weights outside their intended range.",
        },
    ]
)
DIGEST_RESPONSE = json.dumps(
    {
        "headline": "Semantic retrieval moves closer to everyday engineering",
        "narrative": (
            "The most important development is the growing practicality of "
            "semantic retrieval in ordinary engineering systems. Better vector "
            "workflows make it easier to find conceptually related material even "
            "when users do not know the exact vocabulary used by an article.\n\n"
            "Several themes reinforce one another today: hybrid ranking is "
            "becoming a dependable default, preference signals are being used "
            "with more restraint, and evaluation is moving closer to real user "
            "tasks. Together they suggest that useful AI products depend on "
            "careful orchestration rather than one isolated model call.\n\n"
            "Engineers should compare exact and semantic retrieval on their own "
            "queries this week, inspect failure cases, and measure whether learned "
            "preferences improve ordering without hiding diverse sources."
        ),
        "key_themes": [
            "semantic retrieval",
            "hybrid ranking",
            "preference learning",
        ],
    }
)


class FakeQuizClient:
    async def complete(self, prompt: str) -> str:
        return QUIZ_RESPONSE


class FakeDigestClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, prompt: str) -> str:
        self.calls += 1
        return DIGEST_RESPONSE


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_key}


def api_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.fixture(autouse=True)
async def clean_phase7_data():
    await quiz_sessions.clear()
    async with SessionLocal() as session:
        await session.execute(
            delete(DailyDigest).where(
                DailyDigest.date.in_([DIGEST_DATE, EMPTY_DIGEST_DATE])
            )
        )
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()
    yield
    await quiz_sessions.clear()
    async with SessionLocal() as session:
        await session.execute(
            delete(DailyDigest).where(
                DailyDigest.date.in_([DIGEST_DATE, EMPTY_DIGEST_DATE])
            )
        )
        await session.execute(delete(Article).where(Article.source == TEST_SOURCE))
        await session.commit()


async def insert_article(
    *,
    status: str = "done",
    ingested_at: datetime | None = None,
) -> uuid.UUID:
    article_id = uuid.uuid4()
    title = f"Phase 7 article {article_id}"
    url = f"https://example.invalid/phase7/{article_id}"
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
                raw_text="A detailed article about retrieval and ranking systems.",
                summary=(
                    "The article explains semantic retrieval, hybrid ranking, "
                    "and bounded preference updates for an engineering feed."
                    if status == "done"
                    else None
                ),
                category="tools" if status == "done" else None,
                importance=5 if status == "done" else None,
                entities={
                    "models": [],
                    "companies": [],
                    "techniques": ["reciprocal rank fusion"],
                    "datasets": [],
                }
                if status == "done"
                else None,
                keywords=["semantic search", "ranking", "preferences"]
                if status == "done"
                else None,
                enrichment_status=status,
            )
        )
        await session.commit()
    return article_id


async def test_quiz_question_format_and_score_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article_id = await insert_article()

    async def fake_create(article: Article):
        return await create_quiz(article, client=FakeQuizClient())

    monkeypatch.setattr("app.routers.quiz.create_quiz", fake_create)
    async with api_client() as client:
        generated = await client.get(
            f"/quiz/generate/{article_id}",
            headers=auth_headers(),
        )
        submitted = await client.post(
            f"/quiz/{article_id}/submit",
            json={
                "answers": [
                    {"question_id": 1, "selected": "B"},
                    {"question_id": 2, "selected": "D"},
                    {"question_id": 3, "selected": "C"},
                ],
                "duration_seconds": 90,
            },
            headers=auth_headers(),
        )

    assert generated.status_code == 200
    questions = generated.json()["questions"]
    assert len(questions) == 3
    assert all(set(question["options"]) == {"A", "B", "C", "D"} for question in questions)
    assert all(question["correct"] in {"A", "B", "C", "D"} for question in questions)
    assert all(
        text
        for question in questions
        for text in question["options"].values()
    )
    assert submitted.status_code == 200
    assert submitted.json()["score"] == 0.67
    assert submitted.json()["correct_count"] == 2
    assert all(item["feedback"] for item in submitted.json()["results"])

    async with SessionLocal() as session:
        article = await session.get(Article, article_id)
        attempt = await session.scalar(
            select(QuizAttempt).where(QuizAttempt.article_id == article_id)
        )
    assert article.quiz_attempted is True
    assert article.quiz_score == Decimal("0.67")
    assert attempt.score == Decimal("0.67")
    assert attempt.duration_s == 90


async def test_quiz_for_unenriched_article_returns_422() -> None:
    article_id = await insert_article(status="pending")
    async with api_client() as client:
        response = await client.get(
            f"/quiz/generate/{article_id}",
            headers=auth_headers(),
        )

    assert response.status_code == 422
    assert "not been enriched" in response.json()["detail"]


async def test_digest_is_idempotent_and_has_valid_length() -> None:
    await insert_article(ingested_at=datetime(2097, 7, 7, 12, tzinfo=UTC))
    client = FakeDigestClient()

    first = await generate_daily_digest(DIGEST_DATE, client=client)
    second = await generate_daily_digest(DIGEST_DATE, client=client)

    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(DailyDigest)
            .where(DailyDigest.date == DIGEST_DATE)
        )
    assert first is not None
    assert second is not None
    assert count == 1
    assert client.calls == 1
    assert 200 <= len(first.narrative) <= 5000
    assert len(first.headline) <= 200
    assert len(first.narrative.split("\n\n")) == 3


async def test_digest_with_no_recent_articles_creates_no_row() -> None:
    result = await generate_daily_digest(
        EMPTY_DIGEST_DATE,
        client=FakeDigestClient(),
    )

    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(DailyDigest)
            .where(DailyDigest.date == EMPTY_DIGEST_DATE)
        )
    assert result is None
    assert count == 0


def test_single_line_digest_is_normalized_to_three_paragraphs() -> None:
    result = DigestGenerationResult.model_validate(
        {
            "headline": "A valid digest headline",
            "narrative": (
                "The lead development matters because retrieval systems are "
                "becoming practical for ordinary engineering teams. The change "
                "reduces the gap between prototypes and dependable products. "
                "Hybrid ranking and realistic evaluation are emerging together. "
                "Both themes reward careful orchestration over isolated model "
                "calls. Engineers should compare exact and semantic retrieval "
                "on their own queries this week. They should also measure latency, "
                "failure modes, and human review costs before scaling."
            ),
            "key_themes": ["retrieval", "evaluation", "engineering"],
        }
    )

    assert len(result.narrative.split("\n\n")) == 3
