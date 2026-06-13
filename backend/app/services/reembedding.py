from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.enrichment.embedder import call_embedder
from app.models.article import Article


@dataclass(slots=True)
class ReembeddingResult:
    processed: int = 0
    remaining: int = 0


async def reembed_articles(
    batch_size: int = 20,
    article_ids: set[UUID] | None = None,
) -> ReembeddingResult:
    settings = get_settings()
    target_model = settings.embedding_model_name
    conditions = [
        Article.enrichment_status == "done",
        Article.summary.is_not(None),
        Article.embedding_model != target_model,
    ]
    if article_ids is not None:
        conditions.append(Article.id.in_(article_ids))
    async with SessionLocal() as session:
        articles = list(
            (
                await session.scalars(
                    select(Article)
                    .where(*conditions)
                    .order_by(Article.enriched_at, Article.id)
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        for article in articles:
            article.embedding = await call_embedder(article.summary or "")
            article.embedding_model = target_model
            await session.commit()

        remaining = await session.scalar(
            select(Article.id).where(*conditions).limit(1)
        )
    return ReembeddingResult(
        processed=len(articles),
        remaining=1 if remaining is not None else 0,
    )
