import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.ingestion.base import BaseIngestor, RawItem, SourceFetchError
from app.utils.date_parser import parse_date
from app.utils.hash import normalize_url, validate_url
from app.utils.text_cleaner import clean_body, clean_title


logger = logging.getLogger(__name__)


class GitHubTrendingIngestor(BaseIngestor):
    def __init__(
        self,
        trending_url: str,
        search_url: str,
        search_query: str,
        user_agent: str,
    ):
        self.trending_url = validate_url(trending_url)
        self.search_url = validate_url(search_url)
        self.search_query = search_query
        self.user_agent = user_agent

    async def fetch(self) -> list[RawItem]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
        }
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=True, headers=headers
        ) as client:
            results = await self._fetch_payloads(client)

        if not results:
            raise SourceFetchError("Both GitHub sources failed")

        items: dict[str, RawItem] = {}
        for kind, payload in results:
            repositories = self._repositories(kind, payload)
            for repository in repositories:
                item = self._to_item(repository)
                if item is not None:
                    items[normalize_url(item.url)] = item
        return list(items.values())

    async def _fetch_payloads(
        self, client: httpx.AsyncClient
    ) -> list[tuple[str, object]]:
        requests = (
            ("trending", client.get(self.trending_url)),
            (
                "search",
                client.get(
                    self.search_url,
                    params={
                        "q": self.search_query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 10,
                    },
                ),
            ),
        )
        payloads: list[tuple[str, object]] = []
        for kind, request in requests:
            try:
                response = await request
                response.raise_for_status()
                payloads.append((kind, response.json()))
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("GitHub %s fetch failed: %s", kind, exc)
        return payloads

    @staticmethod
    def _repositories(kind: str, payload: object) -> list[dict]:
        if kind == "search" and isinstance(payload, dict):
            values = payload.get("items", [])
        elif isinstance(payload, dict):
            values = payload.get("repositories", payload.get("items", []))
        else:
            values = payload
        return [value for value in values if isinstance(value, dict)]

    def _to_item(self, repo: dict) -> RawItem | None:
        owner_value = repo.get("owner")
        owner = (
            owner_value.get("login", "")
            if isinstance(owner_value, dict)
            else str(owner_value or repo.get("author") or "")
        )
        name = str(repo.get("name") or "")
        full_name = str(repo.get("full_name") or "").strip("/")
        if not full_name and owner and name:
            full_name = f"{owner}/{name}"

        raw_url = repo.get("html_url") or repo.get("url")
        try:
            url = validate_url(str(raw_url or ""))
        except ValueError:
            return None
        if not full_name:
            full_name = url.rstrip("/").rsplit("/", 2)[-2] + "/" + url.rstrip(
                "/"
            ).rsplit("/", 1)[-1]

        description = clean_body(str(repo.get("description") or ""), 1000)
        title = clean_title(
            f"{full_name}: {description or 'No description available'}", 200
        )
        topics = repo.get("topics") or []
        if isinstance(topics, str):
            topics = [topic.strip() for topic in topics.split(",") if topic.strip()]
        stars = repo.get("stargazers_count", repo.get("stars", 0))
        language = repo.get("language") or "Unknown"
        raw_text = clean_body(
            f"{description}. Topics: {', '.join(map(str, topics))}. "
            f"Stars: {stars}. Language: {language}."
        )

        created_at = parse_date(repo.get("created_at"))
        pushed_at = parse_date(
            repo.get("pushed_at") or repo.get("lastBuilt") or repo.get("updated_at")
        )
        cutoff = datetime.now(UTC) - timedelta(days=7)
        published_at = created_at if created_at and created_at >= cutoff else pushed_at
        return RawItem(
            title=title,
            url=url,
            source="github",
            source_id=str(repo.get("id") or full_name),
            published_at=published_at,
            raw_text=raw_text,
            raw_html=None,
        )

