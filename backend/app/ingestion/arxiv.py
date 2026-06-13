import logging
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from app.ingestion.base import BaseIngestor, RawItem, SourceFetchError
from app.utils.date_parser import parse_date
from app.utils.hash import validate_url
from app.utils.text_cleaner import clean_body, clean_title, strip_latex


logger = logging.getLogger(__name__)


class ArxivIngestor(BaseIngestor):
    def __init__(self, api_url: str, categories: list[str], max_results: int = 40):
        self.api_url = validate_url(api_url)
        self.categories = categories
        self.max_results = max_results

    async def fetch(self) -> list[RawItem]:
        if not self.categories:
            raise SourceFetchError("No arXiv categories are configured")
        query = " OR ".join(f"cat:{category}" for category in self.categories)
        try:
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True
            ) as client:
                response = await client.get(
                    self.api_url,
                    params={
                        "search_query": query,
                        "start": 0,
                        "max_results": self.max_results,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceFetchError(f"arXiv request failed: {exc}") from exc

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise SourceFetchError(f"arXiv response parse failed: {parsed.bozo_exception}")

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        items: list[RawItem] = []
        for entry in parsed.entries:
            published_at = parse_date(
                entry.get("published") or entry.get("updated")
            )
            if published_at is None or published_at < cutoff:
                continue

            title = clean_title(strip_latex(clean_title(entry.get("title", ""))))
            try:
                url = validate_url(entry.get("id") or entry.get("link") or "")
            except ValueError:
                continue
            if not title:
                continue

            category = self._category(entry)
            abstract = strip_latex(clean_body(entry.get("summary", "")))
            raw_text = clean_body(f"[arXiv {category}] {abstract}")
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source="arxiv",
                    source_id=url.rstrip("/").rsplit("/", 1)[-1],
                    published_at=published_at,
                    raw_text=raw_text,
                    raw_html=None,
                )
            )
        return items

    def _category(self, entry) -> str:
        terms = [
            tag.get("term")
            for tag in entry.get("tags", [])
            if tag.get("term") in self.categories
        ]
        return str(terms[0] if terms else self.categories[0])

