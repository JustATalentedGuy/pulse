from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import article_response
from app.auth import verify_api_key
from app.config import get_settings
from app.database import get_session
from app.models.article import Article
from app.models.digest import DailyDigest
from app.schemas.article import DigestHistoryItem, DigestResponse


router = APIRouter(
    prefix="/digest",
    tags=["digest"],
    dependencies=[Depends(verify_api_key)],
)


async def _digest_response(
    digest: DailyDigest,
    session: AsyncSession,
) -> DigestResponse:
    article_ids = digest.top_articles or []
    articles = (
        list(
            (
                await session.scalars(
                    select(Article).where(Article.id.in_(article_ids))
                )
            ).all()
        )
        if article_ids
        else []
    )
    by_id = {article.id: article for article in articles}
    return DigestResponse(
        id=digest.id,
        date=digest.date,
        generated_at=digest.generated_at,
        headline=digest.headline,
        narrative=digest.narrative,
        key_themes=digest.key_themes or [],
        top_articles=[
            article_response(by_id[article_id])
            for article_id in article_ids
            if article_id in by_id
        ],
    )


@router.get("/today", response_model=DigestResponse)
async def get_today_digest(
    session: AsyncSession = Depends(get_session),
) -> DigestResponse:
    today = datetime.now(ZoneInfo(get_settings().scheduler_timezone)).date()
    digest = await session.scalar(
        select(DailyDigest).where(DailyDigest.date == today)
    )
    if digest is None:
        raise HTTPException(status_code=404, detail="Today's digest is not available yet")
    return await _digest_response(digest, session)


@router.get("/history", response_model=list[DigestHistoryItem])
async def get_digest_history(
    session: AsyncSession = Depends(get_session),
) -> list[DigestHistoryItem]:
    digests = list(
        (
            await session.scalars(
                select(DailyDigest).order_by(DailyDigest.date.desc())
            )
        ).all()
    )
    return [
        DigestHistoryItem(date=digest.date, headline=digest.headline)
        for digest in digests
    ]


@router.get("/{digest_date}", response_model=DigestResponse)
async def get_digest(
    digest_date: date,
    session: AsyncSession = Depends(get_session),
) -> DigestResponse:
    digest = await session.scalar(
        select(DailyDigest).where(DailyDigest.date == digest_date)
    )
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return await _digest_response(digest, session)
