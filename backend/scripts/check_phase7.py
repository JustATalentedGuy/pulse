import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.digest import DailyDigest


async def main() -> None:
    failed = False
    headers = {"X-API-Key": get_settings().api_key}
    async with SessionLocal() as session:
        article = await session.scalar(
            select(Article)
            .where(
                Article.enrichment_status == "done",
                Article.summary.is_not(None),
            )
            .order_by(Article.importance.desc().nullslast())
            .limit(1)
        )
        digest_count = await session.scalar(
            select(func.count()).select_from(DailyDigest)
        )

    checks = [
        ("an enriched article is available for quiz generation", article is not None),
        ("at least one daily digest exists", (digest_count or 0) > 0),
    ]
    if article is not None:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=60,
        ) as client:
            response = await client.get(
                f"/quiz/generate/{article.id}",
                headers=headers,
            )
        payload = response.json()
        questions = payload.get("questions", [])
        checks.extend(
            [
                ("quiz endpoint returns 200", response.status_code == 200),
                ("quiz contains exactly three questions", len(questions) == 3),
                (
                    "every quiz question has A-D options",
                    all(
                        set(question.get("options", {})) == {"A", "B", "C", "D"}
                        for question in questions
                    ),
                ),
            ]
        )

    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        failed = failed or not passed
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
