from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.utils.text_cleaner import clean_body


class SourceFetchError(RuntimeError):
    """Raised when a source produced no data because every request failed."""


@dataclass(slots=True)
class RawItem:
    title: str
    url: str
    source: str
    source_id: str | None
    published_at: datetime | None
    raw_text: str
    raw_html: str | None


class BaseIngestor(ABC):
    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        """Return successful items and isolate partial source failures."""

    @staticmethod
    def _strip_html(html: str) -> str:
        return clean_body(html)

