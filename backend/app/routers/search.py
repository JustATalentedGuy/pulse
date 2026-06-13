from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import article_response
from app.auth import verify_api_key
from app.database import get_session
from app.config import get_settings
from app.enrichment.embedder import call_embedder, embed
from app.models.article import Article
from app.schemas.article import SearchResponse


SearchMode = Literal["fts", "semantic", "hybrid"]
RankedArticle = tuple[Article, float]
router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


async def full_text_search(
    query_text: str,
    limit: int,
    session: AsyncSession,
) -> tuple[list[RankedArticle], int]:
    document = func.to_tsvector(
        "english",
        Article.title + " " + func.coalesce(Article.summary, ""),
    )
    query = func.plainto_tsquery("english", query_text)
    rank = func.ts_rank(document, query).label("rank")
    conditions = [document.op("@@")(query), Article.hidden.is_(False)]
    total = await session.scalar(
        select(func.count()).select_from(Article).where(*conditions)
    )
    rows = (
        await session.execute(
            select(Article, rank)
            .where(*conditions)
            .order_by(rank.desc(), Article.ingested_at.desc(), Article.id)
            .limit(limit)
        )
    ).all()
    return [(article, float(score)) for article, score in rows], total or 0


async def semantic_search(
    query_text: str,
    limit: int,
    session: AsyncSession,
) -> tuple[list[RankedArticle], int]:
    query_embedding = await call_embedder(query_text, embed)
    embedding_model = get_settings().embedding_model_name
    distance = Article.embedding.cosine_distance(query_embedding)
    similarity = (1.0 - distance).label("similarity")
    conditions = [
        Article.enrichment_status == "done",
        Article.embedding.is_not(None),
        Article.embedding_model == embedding_model,
        Article.hidden.is_(False),
    ]
    total = await session.scalar(
        select(func.count()).select_from(Article).where(*conditions)
    )
    await session.execute(text("SET LOCAL ivfflat.probes = 10"))
    rows = (
        await session.execute(
            select(Article, similarity)
            .where(*conditions)
            .order_by(distance, Article.ingested_at.desc(), Article.id)
            .limit(limit)
        )
    ).all()
    return [(article, float(score)) for article, score in rows], total or 0


def rrf_merge(
    fts_results: Sequence[RankedArticle],
    semantic_results: Sequence[RankedArticle],
    *,
    limit: int,
    k: int = 60,
) -> list[RankedArticle]:
    scores: dict[UUID, float] = {}
    articles: dict[UUID, Article] = {}
    for results in (fts_results, semantic_results):
        for rank, (article, _) in enumerate(results):
            articles[article.id] = article
            scores[article.id] = scores.get(article.id, 0.0) + 1.0 / (
                k + rank + 1
            )
    ranked_ids = sorted(
        scores,
        key=lambda article_id: (
            -scores[article_id],
            -articles[article_id].ingested_at.timestamp(),
            str(article_id),
        ),
    )
    return [
        (articles[article_id], scores[article_id])
        for article_id in ranked_ids[:limit]
    ]


@router.get("", response_model=SearchResponse)
async def search_articles(
    q: str = Query(min_length=2),
    mode: SearchMode = "hybrid",
    limit: int = Query(default=10, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    candidate_limit = min(100, max(30, limit * 4))
    if mode == "fts":
        results, total = await full_text_search(q, limit, session)
    elif mode == "semantic":
        results, total = await semantic_search(q, limit, session)
    else:
        fts_results, _ = await full_text_search(q, candidate_limit, session)
        semantic_results, _ = await semantic_search(
            q,
            candidate_limit,
            session,
        )
        results = rrf_merge(
            fts_results,
            semantic_results,
            limit=limit,
        )
        total = len(
            {
                article.id
                for article, _ in [*fts_results, *semantic_results]
            }
        )

    return SearchResponse(
        query=q,
        mode=mode,
        results=[
            article_response(article, personalized_score=score)
            for article, score in results
        ],
        total=total,
    )
