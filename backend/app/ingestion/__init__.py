from app.ingestion.arxiv import ArxivIngestor
from app.ingestion.github_trending import GitHubTrendingIngestor
from app.ingestion.rss import RssIngestor

__all__ = [
    "ArxivIngestor",
    "GitHubTrendingIngestor",
    "RssIngestor",
]
