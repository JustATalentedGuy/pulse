import re

from app.config import get_settings
from app.ingestion.base import BaseIngestor
from app.utils.hash import compute_hash, normalize_url
from app.utils.text_cleaner import strip_latex


class StubIngestor(BaseIngestor):
    async def fetch(self):
        return []


def test_url_normalization_produces_same_hash_for_tracking_parameter() -> None:
    configured_url = get_settings().rss_feed_entries[0].split("|", 1)[-1]
    separator = "&" if "?" in configured_url else "?"
    tracked_url = f"{configured_url}{separator}utm_source=twitter#section"

    assert normalize_url(configured_url) == normalize_url(tracked_url)
    assert compute_hash("Same article", configured_url) == compute_hash(
        "Same article", tracked_url
    )


def test_strip_html_returns_plain_text() -> None:
    assert StubIngestor._strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_latex_removes_inline_expression() -> None:
    value = r"We propose $f(x) = \sigma(Wx + b)$ for classification"
    assert strip_latex(value) == "We propose  for classification"


def test_strip_html_removes_tags_and_extra_whitespace() -> None:
    result = StubIngestor._strip_html("<div>  one\n <span>two</span> </div>")
    assert result == "one two"
    assert re.search(r"<[^>]+>", result) is None

