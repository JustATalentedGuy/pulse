from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


CategoryKey = Literal[
    "models",
    "research",
    "tools",
    "cloud",
    "industry",
    "other",
]


class EntityMapSchema(BaseModel):
    models: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    url: str
    source: str
    source_domain: str
    published_at: datetime | None
    ingested_at: datetime
    summary: str | None
    category: CategoryKey | None
    importance: int | None
    entities: EntityMapSchema = Field(default_factory=EntityMapSchema)
    keywords: list[str] = Field(default_factory=list)
    bookmarked: bool
    read_at: datetime | None
    read_duration_s: int | None
    quiz_attempted: bool
    personalized_score: float | None


class FeedResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    has_more: bool
    next_offset: int


class SearchResponse(BaseModel):
    query: str
    mode: Literal["fts", "semantic", "hybrid"] = "hybrid"
    results: list[ArticleResponse]
    total: int


class DigestResponse(BaseModel):
    id: UUID
    date: date
    generated_at: datetime
    headline: str | None
    narrative: str | None
    key_themes: list[str] = Field(default_factory=list)
    top_articles: list[ArticleResponse] = Field(default_factory=list)


class DigestHistoryItem(BaseModel):
    date: date
    headline: str | None


class ReadEventRequest(BaseModel):
    duration_seconds: int = Field(ge=1, le=7200)


class StatusResponse(BaseModel):
    status: str
    db_connected: bool
    articles_total: int
    articles_enriched: int
    articles_pending: int
    groq_quota_used_today: int
    groq_quota_limit: int
    last_ingestion: datetime | None
    scheduler_jobs: list[dict[str, str | None]]
