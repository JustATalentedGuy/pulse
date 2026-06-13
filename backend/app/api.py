from urllib.parse import urlparse

from app.models.article import Article
from app.schemas.article import ArticleResponse, EntityMapSchema


def article_response(
    article: Article,
    *,
    personalized_score: float | None = None,
) -> ArticleResponse:
    entities = article.entities or {}
    return ArticleResponse(
        id=article.id,
        title=article.title,
        url=article.url,
        source=article.source,
        source_domain=urlparse(article.url).netloc.lower(),
        published_at=article.published_at,
        ingested_at=article.ingested_at,
        summary=article.summary,
        category=article.category,
        importance=article.importance,
        entities=EntityMapSchema(
            models=entities.get("models", []),
            companies=entities.get("companies", []),
            techniques=entities.get("techniques", []),
            datasets=entities.get("datasets", []),
        ),
        keywords=article.keywords or [],
        bookmarked=article.bookmarked,
        read_at=article.read_at,
        read_duration_s=article.read_duration_s,
        quiz_attempted=article.quiz_attempted,
        personalized_score=personalized_score,
    )
