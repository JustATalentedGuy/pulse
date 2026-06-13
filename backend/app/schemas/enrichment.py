from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.utils.text_cleaner import clean_body


ALLOWED_CATEGORIES = {
    "models",
    "research",
    "tools",
    "cloud",
    "industry",
    "other",
}


def _clean_string_list(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = clean_body(value, 100).strip()
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
        if len(cleaned) >= limit:
            break
    return cleaned


class EntityMap(BaseModel):
    models: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)

    @field_validator("models", "companies", "techniques", "datasets", mode="before")
    @classmethod
    def validate_entities(cls, value: Any) -> list[str]:
        return _clean_string_list(value, limit=30)


class EnrichmentResult(BaseModel):
    summary: str = Field(min_length=10, max_length=1000)
    category: str
    importance: int = Field(ge=1, le=5)
    entities: EntityMap = Field(default_factory=EntityMap)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in ALLOWED_CATEGORIES else "other"

    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, value: Any) -> list[str]:
        cleaned = _clean_string_list(value, limit=8)
        return [keyword.lower()[:50] for keyword in cleaned]

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: Any) -> str:
        cleaned = clean_body(str(value or ""), 1000).strip()
        if cleaned and "." not in cleaned:
            cleaned += "."
        return cleaned

