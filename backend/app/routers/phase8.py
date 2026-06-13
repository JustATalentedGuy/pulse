import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.database import get_session
from app.models.trend import TrendingTopic
from app.schemas.phase8 import (
    AskRequest,
    AskResponse,
    PushTokenRequest,
    TrendResponse,
)
from app.services.ask import AskQuotaExhausted, answer_question
from app.services.settings import store_push_token


logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/trends", response_model=list[TrendResponse], tags=["trends"])
async def get_trends(
    session: AsyncSession = Depends(get_session),
) -> list[TrendingTopic]:
    return list(
        (
            await session.scalars(
                select(TrendingTopic).order_by(
                    TrendingTopic.mention_count.desc(),
                    TrendingTopic.name,
                )
            )
        ).all()
    )


@router.post("/user/push-token", tags=["user"])
async def save_push_token(
    payload: PushTokenRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await store_push_token(session, payload.token)
    return {"status": "stored"}


@router.post("/ask", response_model=AskResponse, tags=["ask"])
async def ask_corpus(
    payload: AskRequest,
    session: AsyncSession = Depends(get_session),
) -> AskResponse:
    try:
        return await answer_question(session, payload)
    except AskQuotaExhausted as exc:
        raise HTTPException(
            status_code=503,
            detail="Groq quota exhausted for today. Try again tomorrow.",
        ) from exc
    except Exception as exc:
        logger.exception("Ask endpoint failed")
        raise HTTPException(
            status_code=503,
            detail="Ask mode is temporarily unavailable. Try again later.",
        ) from exc
