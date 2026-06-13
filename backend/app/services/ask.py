from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.groq import GroqChatClient
from app.config import get_settings
from app.enrichment.embedder import call_embedder, embed
from app.enrichment.quota_manager import QuotaManager, reserve_quota
from app.models.article import Article
from app.schemas.phase8 import AskRequest, AskResponse, AskSource


MINIMUM_RELEVANCE = 0.45


class AskClient(Protocol):
    async def complete(self, prompt: str) -> str: ...


class AskQuotaExhausted(RuntimeError):
    pass


async def retrieve_context(
    session: AsyncSession,
    question: str,
    *,
    limit: int = 5,
    minimum_relevance: float = MINIMUM_RELEVANCE,
) -> list[tuple[Article, float]]:
    query_embedding = await call_embedder(question, embed)
    embedding_model = get_settings().embedding_model_name
    distance = Article.embedding.cosine_distance(query_embedding)
    similarity = (1.0 - distance).label("similarity")
    await session.execute(text("SET LOCAL ivfflat.probes = 10"))
    rows = (
        await session.execute(
            select(Article, similarity)
            .where(
                Article.enrichment_status == "done",
                Article.embedding.is_not(None),
                Article.embedding_model == embedding_model,
                Article.hidden.is_(False),
            )
            .order_by(distance, Article.ingested_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        (article, float(score))
        for article, score in rows
        if float(score) >= minimum_relevance
    ]


def build_ask_prompt(
    payload: AskRequest,
    contexts: list[tuple[Article, float]],
) -> str:
    context = "\n".join(
        f"[{article.id}] {article.title}: {article.summary}"
        for article, _ in contexts
    )
    history = "\n".join(
        f"{message.role.upper()}: {message.content}"
        for message in payload.conversation_history[-6:]
    )
    return f"""Answer the user's question using only the article context below.
If the context does not support a claim, say so. Cite supporting articles
inline using their bracketed UUIDs. Keep the answer concise and practical.

ARTICLE CONTEXT:
{context}

RECENT CONVERSATION:
{history or "None"}

USER QUESTION:
{payload.question}
"""


async def answer_question(
    session: AsyncSession,
    payload: AskRequest,
    *,
    client: AskClient | None = None,
    quota_manager: QuotaManager | None = None,
    minimum_relevance: float = MINIMUM_RELEVANCE,
) -> AskResponse:
    contexts = await retrieve_context(
        session,
        payload.question,
        minimum_relevance=minimum_relevance,
    )
    if not contexts:
        return AskResponse(
            answer=(
                "I do not have relevant information in the stored article "
                "corpus to answer that question."
            ),
            sources=[],
            used_groq=False,
        )

    settings = get_settings()
    ask_client = client
    if ask_client is None:
        if not await reserve_quota(quota_manager, settings):
            raise AskQuotaExhausted
        ask_client = GroqChatClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    elif quota_manager is not None and not await reserve_quota(
        quota_manager,
        settings,
    ):
        raise AskQuotaExhausted

    answer = await ask_client.complete(build_ask_prompt(payload, contexts))
    return AskResponse(
        answer=answer.strip(),
        sources=[
            AskSource(
                id=article.id,
                title=article.title,
                url=article.url,
                similarity=round(similarity, 4),
            )
            for article, similarity in contexts
        ],
        used_groq=True,
    )
