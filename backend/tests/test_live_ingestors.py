import re
import pytest

from app.config import get_settings
from app.ingestion.arxiv import ArxivIngestor
from app.ingestion.github_trending import GitHubTrendingIngestor
from app.ingestion.rss import RssIngestor


settings = get_settings()


@pytest.mark.live
async def test_rss_ingestor_live() -> None:
    ingestor = RssIngestor(settings.rss_feed_entries[:1])
    items = await ingestor.fetch()

    assert items
    assert all(item.title and item.url.startswith("http") for item in items)
    assert all(re.search(r"<[^>]+>", item.raw_text) is None for item in items)


@pytest.mark.live
async def test_github_ingestor_live() -> None:
    ingestor = GitHubTrendingIngestor(
        settings.github_trending_url,
        settings.github_search_url,
        settings.github_search_query,
        settings.github_user_agent,
    )
    items = await ingestor.fetch()

    assert items
    assert all(item.source == "github" for item in items)


@pytest.mark.live
async def test_arxiv_ingestor_live() -> None:
    ingestor = ArxivIngestor(
        settings.arxiv_api_url,
        settings.arxiv_category_list,
        settings.arxiv_max_results,
    )
    items = await ingestor.fetch()

    assert all(item.source == "arxiv" for item in items)
    assert all("$" not in item.raw_text for item in items)
