import asyncio
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import article_response
from app.auth import verify_api_key
from app.database import get_session
from app.models.article import Article
from app.schemas.article import (
    ArticleResponse,
    CategoryKey,
    FeedResponse,
    ReadEventRequest,
)
from app.services.preferences import update_preference_after_read
from app.services.ranking import (
    load_preference_profile,
    personalized_score,
    personalized_score_expression,
)


router = APIRouter(
    prefix="/feed",
    tags=["feed"],
    dependencies=[Depends(verify_api_key)],
)
background_tasks: set[asyncio.Task[None]] = set()


def _track_task(task: asyncio.Task[None]) -> None:
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


@router.get("", response_model=FeedResponse)
async def get_feed(
    category: CategoryKey | None = None,
    min_importance: int = Query(default=1, ge=1, le=5),
    limit: int = Query(default=20, ge=10, le=50),
    offset: int = Query(default=0, ge=0),
    since: datetime | None = None,
    show_read: bool = True,
    show_hidden: bool = False,
    session: AsyncSession = Depends(get_session),
) -> FeedResponse:
    conditions = [func.coalesce(Article.importance, 1) >= min_importance]
    if category is not None:
        conditions.append(Article.category == category)
    if since is not None:
        conditions.append(Article.ingested_at > since)
    if not show_read:
        conditions.append(Article.read_at.is_(None))
    if not show_hidden:
        conditions.append(Article.hidden.is_(False))

    total = await session.scalar(
        select(func.count()).select_from(Article).where(*conditions)
    )
    profile = await load_preference_profile(session)
    score = personalized_score_expression(profile).label("personalized_score")
    ordering = (
        (
            func.coalesce(Article.importance, 3).desc(),
            Article.ingested_at.desc(),
            Article.id,
        )
        if profile.cold_start
        else (score.desc(), Article.ingested_at.desc(), Article.id)
    )
    rows = (
        await session.execute(
            select(Article, score)
            .where(*conditions)
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    item_count = len(rows)
    total_count = total or 0
    return FeedResponse(
        items=[
            article_response(article, personalized_score=float(item_score))
            for article, item_score in rows
        ],
        total=total_count,
        has_more=offset + item_count < total_count,
        next_offset=offset + item_count,
    )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ArticleResponse:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    profile = await load_preference_profile(session)
    score = personalized_score(article, profile)
    return article_response(article, personalized_score=score)


@router.post("/{article_id}/read")
async def record_read(
    article_id: UUID,
    payload: ReadEventRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article.read_at = datetime.now(UTC)
    article.read_duration_s = payload.duration_seconds
    await session.commit()
    task = asyncio.create_task(
        update_preference_after_read(article_id, payload.duration_seconds)
    )
    _track_task(task)
    return {"status": "recorded"}


@router.post("/{article_id}/bookmark")
async def toggle_bookmark(
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article.bookmarked = not article.bookmarked
    article.bookmarked_at = datetime.now(UTC) if article.bookmarked else None
    await session.commit()
    return {"bookmarked": article.bookmarked}


@router.post("/{article_id}/hide")
async def hide_article(
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article.hidden = True
    await session.commit()
    return {"status": "hidden"}
