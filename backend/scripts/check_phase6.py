import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.preference import Preference


async def main() -> None:
    failed = False
    headers = {"X-API-Key": get_settings().api_key}
    async with SessionLocal() as session:
        vector_version = await session.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        )
        missing_embeddings = await session.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.enrichment_status == "done",
                Article.embedding.is_(None),
            )
        )
        preference = await session.scalar(select(Preference).limit(1))

    checks = [
        ("pgvector extension is active", vector_version is not None),
        ("all enriched articles have embeddings", missing_embeddings == 0),
        ("preference row exists", preference is not None),
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for mode in ("fts", "semantic", "hybrid"):
            response = await client.get(
                "/search",
                params={"q": "AI agents", "mode": mode, "limit": 5},
                headers=headers,
            )
            checks.append(
                (
                    f"{mode} search returns 200 and the requested mode",
                    response.status_code == 200
                    and response.json().get("mode") == mode,
                )
            )

    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        failed = failed or not passed
    if preference is not None:
        print(
            "Preference weights:",
            preference.w_models,
            preference.w_research,
            preference.w_tools,
            preference.w_cloud,
            preference.w_industry,
        )
        print("Interest terms:", len(preference.interest_terms or []))

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
