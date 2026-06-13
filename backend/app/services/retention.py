from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update

from app.config import get_settings
from app.database import SessionLocal
from app.models.article import Article
from app.models.ingestion_run import IngestionRun
from app.models.quiz import QuizSession


@dataclass(slots=True)
class RetentionResult:
    raw_html_cleared: int
    expired_quiz_sessions_deleted: int
    skipped_articles_deleted: int
    old_articles_deleted: int
    ingestion_runs_deleted: int

    def model_dump(self) -> dict[str, int]:
        return asdict(self)


async def apply_retention(source: str | None = None) -> RetentionResult:
    settings = get_settings()
    now = datetime.now(UTC)
    article_scope = [Article.source == source] if source else []
    async with SessionLocal() as session:
        raw_html = await session.execute(
            update(Article)
            .where(
                *article_scope,
                Article.enrichment_status == "done",
                Article.raw_html.is_not(None),
            )
            .values(raw_html=None)
        )
        quiz_sessions = await session.execute(
            delete(QuizSession).where(QuizSession.expires_at <= now)
        )
        skipped = await session.execute(
            delete(Article).where(
                *article_scope,
                Article.enrichment_status == "skipped",
                Article.ingested_at
                < now - timedelta(days=settings.skipped_retention_days),
            )
        )
        old_articles = await session.execute(
            delete(Article).where(
                *article_scope,
                Article.ingested_at
                < now - timedelta(days=settings.article_retention_days)
            )
        )
        if source is None:
            ingestion_runs = await session.execute(
                delete(IngestionRun).where(
                    IngestionRun.started_at
                    < now - timedelta(
                        days=settings.ingestion_run_retention_days
                    )
                )
            )
            ingestion_runs_deleted = ingestion_runs.rowcount
        else:
            ingestion_runs_deleted = 0
        await session.commit()
    return RetentionResult(
        raw_html_cleared=raw_html.rowcount,
        expired_quiz_sessions_deleted=quiz_sessions.rowcount,
        skipped_articles_deleted=skipped.rowcount,
        old_articles_deleted=old_articles.rowcount,
        ingestion_runs_deleted=ingestion_runs_deleted,
    )
