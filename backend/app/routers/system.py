import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.config import get_settings
from app.database import get_session
from app.enrichment.quota_manager import get_quota_usage
from app.ingestion.runner import run_pipeline
from app.models.article import Article
from app.models.ingestion_run import IngestionRun
from app.scheduler.jobs import scheduler
from app.schemas.article import StatusResponse


router = APIRouter(tags=["system"])


@router.get("/status", response_model=StatusResponse)
async def get_status(
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    await session.execute(text("SELECT 1"))
    total, enriched, pending, last_ingestion = (
        await session.execute(
            select(
                func.count(Article.id),
                func.count(Article.id).filter(Article.enrichment_status == "done"),
                func.count(Article.id).filter(Article.enrichment_status == "pending"),
                select(func.max(IngestionRun.completed_at)).scalar_subquery(),
            )
        )
    ).one()
    settings = get_settings()
    quota_usage = await get_quota_usage(settings=settings)
    return StatusResponse(
        status="ok",
        db_connected=True,
        articles_total=total,
        articles_enriched=enriched,
        articles_pending=pending,
        groq_quota_used_today=quota_usage,
        groq_quota_limit=settings.groq_daily_limit,
        last_ingestion=last_ingestion,
        scheduler_jobs=[
            {
                "id": job.id,
                "next_run": (
                    job.next_run_time.isoformat()
                    if getattr(job, "next_run_time", None)
                    else None
                ),
            }
            for job in scheduler.get_jobs()
            if settings.scheduler_enabled
        ],
    )


@router.post(
    "/ingest/trigger",
    dependencies=[Depends(verify_api_key)],
)
async def trigger_ingestion() -> dict[str, str]:
    asyncio.create_task(run_pipeline())
    return {"status": "triggered"}
