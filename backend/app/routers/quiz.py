import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.database import get_session
from app.models.article import Article
from app.schemas.quiz import (
    QuizGenerationResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.quiz import QuizQuotaExhausted, create_quiz, submit_quiz


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/quiz",
    tags=["quiz"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/generate/{article_id}",
    response_model=QuizGenerationResponse,
)
async def generate_article_quiz(
    article_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> QuizGenerationResponse:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.enrichment_status != "done" or not article.summary:
        raise HTTPException(
            status_code=422,
            detail="Article has not been enriched yet. Quiz cannot be generated.",
        )
    try:
        questions = await create_quiz(article)
    except QuizQuotaExhausted as exc:
        raise HTTPException(
            status_code=503,
            detail="Groq quota exhausted for today. Try again tomorrow.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Quiz generation failed for article %s", article_id)
        raise HTTPException(
            status_code=503,
            detail="Quiz generation is temporarily unavailable. Try again later.",
        ) from exc
    return QuizGenerationResponse(
        article_id=article.id,
        article_title=article.title,
        questions=questions,
    )


@router.post(
    "/{article_id}/submit",
    response_model=QuizSubmitResponse,
)
async def submit_article_quiz(
    article_id: UUID,
    payload: QuizSubmitRequest,
    session: AsyncSession = Depends(get_session),
) -> QuizSubmitResponse:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    try:
        return await submit_quiz(
            session,
            article,
            payload.answers,
            payload.duration_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
