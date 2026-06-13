from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    database_host_override: str = ""
    database_ssl: bool = False
    database_ssl_mode: Literal["require", "verify-ca", "verify-full"] = (
        "verify-full"
    )
    database_pool_size: int = Field(default=3, ge=1, le=10)
    database_max_overflow: int = Field(default=2, ge=0, le=10)
    groq_api_key: str = ""
    groq_model: str
    groq_daily_limit: int = Field(default=900, ge=0)
    groq_request_delay_seconds: float = Field(default=2.1, ge=0)
    groq_quota_file: str
    groq_quota_backend: str = "file"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    newsletter_senders: str = (
        "thesequence.substack.com,deeplearning.ai,tldr.tech"
    )
    api_key: str
    log_level: str = "INFO"

    rss_feeds: str
    github_trending_url: str
    github_search_url: str
    github_search_query: str
    github_user_agent: str
    arxiv_api_url: str
    arxiv_categories: str
    arxiv_max_results: int = Field(default=40, ge=1, le=100)
    enrichment_batch_size: int = Field(default=20, ge=1, le=100)
    scheduler_timezone: str = "Asia/Kolkata"
    scheduler_enabled: bool = True
    embedding_provider: str = "local"
    embedding_api_url: str = ""
    embedding_api_secret: str = ""
    embedding_request_timeout_seconds: float = Field(default=30, ge=1, le=120)
    job_secret: str = ""
    article_retention_days: int = Field(default=180, ge=30)
    skipped_retention_days: int = Field(default=30, ge=1)
    ingestion_run_retention_days: int = Field(default=30, ge=1)

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @property
    def rss_feed_entries(self) -> list[str]:
        return self._csv(self.rss_feeds)

    @property
    def arxiv_category_list(self) -> list[str]:
        return self._csv(self.arxiv_categories)

    @property
    def newsletter_sender_list(self) -> list[str]:
        return [sender.lower() for sender in self._csv(self.newsletter_senders)]

    @property
    def database_connection_url(self) -> str:
        url = make_url(self.database_url)
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+asyncpg")
        if self.database_host_override:
            url = url.set(host=self.database_host_override)
        if self.database_ssl:
            url = url.set(
                query={
                    key: value
                    for key, value in url.query.items()
                    if key not in {"ssl", "sslmode"}
                }
            )
        return url.render_as_string(hide_password=False)

    @property
    def database_connect_args(self) -> dict[str, str]:
        if not self.database_ssl:
            return {}
        return {"ssl": self.database_ssl_mode}

    @property
    def embedding_model_name(self) -> str:
        if self.embedding_provider == "supabase":
            return "gte-small"
        return "all-MiniLM-L6-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
