from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import article_response
from app.auth import verify_api_key
from app.database import get_session
from app.models.article import Article
from app.schemas.article import FeedResponse


router = APIRouter(
    prefix="/bookmarks",
    tags=["bookmarks"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=FeedResponse)
async def get_bookmarks(
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> FeedResponse:
    conditions = [Article.bookmarked.is_(True), Article.hidden.is_(False)]
    total = await session.scalar(
        select(func.count()).select_from(Article).where(*conditions)
    )
    articles = list(
        (
            await session.scalars(
                select(Article)
                .where(*conditions)
                .order_by(Article.bookmarked_at.desc(), Article.ingested_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    total_count = total or 0
    return FeedResponse(
        items=[article_response(article) for article in articles],
        total=total_count,
        has_more=offset + len(articles) < total_count,
        next_offset=offset + len(articles),
    )
