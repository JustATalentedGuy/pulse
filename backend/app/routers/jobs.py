import secrets
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.enrichment.worker import enrich_pending
from app.ingestion.runner import run_pipeline
from app.services.digest import generate_daily_digest
from app.services.reembedding import reembed_articles
from app.services.retention import apply_retention
from app.services.trends import detect_trends


async def verify_job_secret(
    job_secret: str | None = Header(default=None, alias="X-Job-Secret"),
) -> str:
    expected = get_settings().job_secret
    if (
        not expected
        or not job_secret
        or not secrets.compare_digest(job_secret, expected)
    ):
        raise HTTPException(status_code=403, detail="Invalid job secret")
    return job_secret


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(verify_job_secret)],
)


async def run_locked(
    session: AsyncSession,
    name: str,
    job: Callable[[], Awaitable[Any]],
) -> tuple[bool, Any]:
    acquired = await session.scalar(
        text("SELECT pg_try_advisory_lock(hashtext(:name))"),
        {"name": f"pulse:{name}"},
    )
    if not acquired:
        return False, None
    try:
        return True, await job()
    finally:
        await session.execute(
            text("SELECT pg_advisory_unlock(hashtext(:name))"),
            {"name": f"pulse:{name}"},
        )


@router.post("/heartbeat")
async def heartbeat() -> dict[str, str]:
    return {"status": "awake"}


@router.post("/ingest")
async def ingest(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await run_pipeline(sources={"rss", "github", "arxiv"})

    started, _ = await run_locked(session, "ingest", job)
    return {"status": "completed" if started else "already_running"}


@router.post("/gmail")
async def gmail(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await run_pipeline(sources={"gmail"})

    started, _ = await run_locked(session, "gmail", job)
    return {"status": "completed" if started else "already_running"}


@router.post("/enrich")
async def enrich(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()

    async def job():
        return await enrich_pending(
            batch_size=settings.enrichment_batch_size
        )

    started, result = await run_locked(session, "enrich", job)
    if not started:
        return {"status": "already_running"}
    return {"status": "completed", **asdict(result)}


@router.post("/reembed")
async def reembed(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await reembed_articles()

    started, result = await run_locked(session, "reembed", job)
    if not started:
        return {"status": "already_running"}
    return {
        "status": "completed",
        "processed": result.processed,
        "remaining": result.remaining,
    }


@router.post("/trends")
async def trends(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await detect_trends(session)

    started, result = await run_locked(session, "trends", job)
    return {
        "status": "completed" if started else "already_running",
        "topics": len(result) if started else 0,
    }


@router.post("/digest")
async def digest(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await generate_daily_digest()

    started, result = await run_locked(session, "digest", job)
    return {
        "status": "completed" if started else "already_running",
        "date": result.date.isoformat() if result is not None else None,
    }


@router.post("/retention")
async def retention(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    async def job():
        return await apply_retention()

    started, result = await run_locked(session, "retention", job)
    if not started:
        return {"status": "already_running"}
    return {"status": "completed", **result.model_dump()}
