import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.enrichment.worker import enrich_pending
from app.ingestion.runner import run_pipeline
from app.services.digest import DigestQuotaExhausted, generate_daily_digest
from app.database import SessionLocal
from app.services.trends import detect_trends


logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler(
    timezone=settings.scheduler_timezone,
    job_defaults={"coalesce": True, "max_instances": 1},
)


async def run_all_ingestors() -> None:
    await run_pipeline(sources={"rss", "github", "arxiv"})


async def run_enrichment() -> None:
    await enrich_pending(batch_size=get_settings().enrichment_batch_size)


async def run_gmail_ingestor() -> None:
    await run_pipeline(sources={"gmail"})


async def generate_digest() -> None:
    try:
        digest = await generate_daily_digest()
    except DigestQuotaExhausted:
        logger.warning("Daily digest skipped because the Groq quota is exhausted")
        return
    except Exception:
        logger.exception("Daily digest generation failed")
        return
    if digest is None:
        logger.info("Daily digest skipped because no enriched articles are available")
    else:
        logger.info("Daily digest generated for %s", digest.date)


async def generate_weekly_summary() -> None:
    logger.info("Weekly summary generation is registered for Phase 7 implementation")


async def run_trend_detection() -> None:
    async with SessionLocal() as session:
        trends = await detect_trends(session)
    logger.info("Trend detection stored %s topics", len(trends))


scheduler.add_job(
    run_all_ingestors,
    "interval",
    hours=2,
    id="ingest_all",
    replace_existing=True,
)
scheduler.add_job(
    run_enrichment,
    "interval",
    minutes=30,
    id="enrich_pending",
    replace_existing=True,
)
scheduler.add_job(
    run_gmail_ingestor,
    "interval",
    hours=4,
    id="gmail_check",
    replace_existing=True,
)
scheduler.add_job(
    generate_digest,
    "cron",
    hour=7,
    minute=0,
    id="daily_digest",
    replace_existing=True,
)
scheduler.add_job(
    run_trend_detection,
    "cron",
    hour=1,
    minute=0,
    id="detect_trends",
    replace_existing=True,
)
scheduler.add_job(
    generate_weekly_summary,
    "cron",
    day_of_week="sun",
    hour=8,
    minute=0,
    id="weekly_summary",
    replace_existing=True,
)
