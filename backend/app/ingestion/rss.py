import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import feedparser

from app.ingestion.base import BaseIngestor, RawItem, SourceFetchError
from app.utils.date_parser import parse_date, parse_struct_time
from app.utils.hash import validate_url
from app.utils.text_cleaner import clean_title


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeedConfig:
    source: str
    url: str


def parse_feed_config(value: str) -> FeedConfig:
    if "|" in value:
        source, url = value.split("|", 1)
        return FeedConfig(source=source.strip()[:100], url=validate_url(url))
    url = validate_url(value)
    hostname = urlparse(url).hostname or "rss"
    return FeedConfig(source=hostname.removeprefix("www.")[:100], url=url)


class RssIngestor(BaseIngestor):
    def __init__(self, feeds: list[str]):
        self.feeds = [parse_feed_config(feed) for feed in feeds]

    async def fetch(self) -> list[RawItem]:
        if not self.feeds:
            raise SourceFetchError("No RSS feeds are configured")

        results = await asyncio.gather(
            *(asyncio.to_thread(feedparser.parse, feed.url) for feed in self.feeds),
            return_exceptions=True,
        )
        items: list[RawItem] = []
        failures = 0
        for feed, result in zip(self.feeds, results, strict=True):
            if isinstance(result, Exception):
                failures += 1
                logger.error("RSS fetch failed for %s: %s", feed.source, result)
                continue
            if result.bozo and not result.entries:
                failures += 1
                logger.error(
                    "RSS parse failed for %s: %s",
                    feed.source,
                    result.get("bozo_exception"),
                )
                continue
            items.extend(self._parse_entries(feed, result.entries))

        if failures == len(self.feeds):
            raise SourceFetchError("Every configured RSS feed failed")
        return items

    def _parse_entries(self, feed: FeedConfig, entries: list) -> list[RawItem]:
        items: list[RawItem] = []
        for entry in entries:
            title = clean_title(entry.get("title", ""))
            if not title:
                continue
            try:
                url = validate_url(entry.get("link", ""))
            except ValueError:
                continue

            raw_html = self._entry_html(entry)
            published_at = parse_struct_time(entry.get("published_parsed"))
            if published_at is None:
                published_at = parse_struct_time(entry.get("updated_parsed"))
            if published_at is None:
                published_at = parse_date(
                    entry.get("published") or entry.get("updated")
                )

            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source=feed.source,
                    source_id=str(entry.get("id") or "") or None,
                    published_at=published_at,
                    raw_text=self._strip_html(raw_html or ""),
                    raw_html=raw_html,
                )
            )
        return items

    @staticmethod
    def _entry_html(entry) -> str | None:
        content = entry.get("content") or []
        if content and content[0].get("value"):
            return str(content[0].get("value"))
        summary = entry.get("summary")
        return str(summary) if summary else None

