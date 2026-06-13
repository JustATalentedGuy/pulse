import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.preference import Preference
from app.scheduler.jobs import scheduler
from app.services.preferences import ensure_preference_row


async def main() -> None:
    failed = False
    settings = get_settings()
    headers = {"X-API-Key": settings.api_key}
    await ensure_preference_row()

    async with SessionLocal() as session:
        categories = set(
            (
                await session.scalars(
                    select(Article.category)
                    .where(
                        Article.enrichment_status == "done",
                        Article.category.is_not(None),
                    )
                    .distinct()
                )
            ).all()
        )
        required = {"models", "research", "tools", "cloud", "industry"}
        missing = required - categories
        print(
            "PASS: all Phase 4 categories are present"
            if not missing
            else f"FAIL: missing enriched categories: {sorted(missing)}"
        )
        failed = failed or bool(missing)

        preference_count = await session.scalar(
            select(func.count()).select_from(Preference)
        )
        print(f"Preference rows: {preference_count}")
        if preference_count != 1:
            failed = True
            print("FAIL: expected exactly one preference row")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await client.get("/feed")
        feed = await client.get("/feed", headers=headers, params={"limit": 10})
        status = await client.get("/status")

    checks = [
        ("missing API key is rejected", rejected.status_code == 403),
        ("feed returns 200", feed.status_code == 200),
        ("feed returns 10 articles", len(feed.json().get("items", [])) == 10),
        ("status endpoint returns 200", status.status_code == 200),
    ]
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        failed = failed or not passed

    job_ids = {job.id for job in scheduler.get_jobs()}
    expected_jobs = {
        "ingest_all",
        "enrich_pending",
        "gmail_check",
        "daily_digest",
        "weekly_summary",
    }
    jobs_ok = job_ids == expected_jobs
    print(
        "PASS: all five scheduler jobs are registered"
        if jobs_ok
        else f"FAIL: scheduler jobs are {sorted(job_ids)}"
    )
    failed = failed or not jobs_ok

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
