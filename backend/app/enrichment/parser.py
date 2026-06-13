import json
import re
from typing import Any

from app.schemas.enrichment import EnrichmentResult


FENCE_START_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
FENCE_END_RE = re.compile(r"\s*```$", re.IGNORECASE)
TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def extract_json(text: str) -> dict[str, Any]:
    cleaned = FENCE_START_RE.sub("", text.strip())
    cleaned = FENCE_END_RE.sub("", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in LLM output: {cleaned[:200]}")
    candidate = TRAILING_COMMA_RE.sub(r"\1", cleaned[start : end + 1])
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in LLM output: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM output JSON must be an object")
    return parsed


def extract_json_array(text: str) -> list[Any]:
    cleaned = FENCE_START_RE.sub("", text.strip())
    cleaned = FENCE_END_RE.sub("", cleaned)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON array found in LLM output: {cleaned[:200]}")
    candidate = TRAILING_COMMA_RE.sub(r"\1", cleaned[start : end + 1])
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in LLM output: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("LLM output JSON must be an array")
    return parsed


def parse_enrichment(text: str) -> EnrichmentResult:
    return EnrichmentResult.model_validate(extract_json(text))
