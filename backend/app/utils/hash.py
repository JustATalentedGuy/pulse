import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    params = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    )
    clean = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(params, doseq=True),
        fragment="",
    )
    return urlunparse(clean).rstrip("/")


def validate_url(url: str) -> str:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if len(normalized) > 2048:
        raise ValueError("URL exceeds 2048 characters")
    return normalized


def compute_hash(title: str, url: str) -> str:
    normalized = title.strip().lower() + normalize_url(url).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

