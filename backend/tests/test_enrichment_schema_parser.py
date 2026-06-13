import pytest
from pydantic import ValidationError

from app.enrichment.parser import extract_json
from app.schemas.enrichment import EnrichmentResult


VALID_JSON = (
    '{"summary":"A model was released. It helps AI engineers.",'
    '"category":"models","importance":4,'
    '"entities":{"models":[],"companies":[],"techniques":[],"datasets":[]},'
    '"keywords":["AI","Model"]}'
)


@pytest.mark.parametrize(
    "value",
    [
        VALID_JSON,
        f"```json\n{VALID_JSON}\n```",
        f"Here is the analysis: {VALID_JSON}",
        f"<analysis_json>{VALID_JSON}</analysis_json>",
    ],
)
def test_extract_json_resilient_inputs(value: str) -> None:
    assert extract_json(value)["category"] == "models"


def test_extract_json_strips_trailing_commas() -> None:
    assert extract_json('{"category":"tools",}') == {"category": "tools"}


def test_extract_json_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="No JSON object"):
        extract_json("This response contains no structured data")


def test_category_falls_back_to_other() -> None:
    result = EnrichmentResult(
        summary="A release happened. It matters to engineers.",
        category="breaking_news",
        importance=3,
        entities={},
        keywords=["AI"],
    )
    assert result.category == "other"


def test_importance_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        EnrichmentResult(
            summary="A release happened. It matters to engineers.",
            category="models",
            importance=7,
            entities={},
            keywords=[],
        )


def test_entities_and_keywords_remove_empty_values() -> None:
    result = EnrichmentResult(
        summary="Claude 4 was adapted with LoRA. The approach matters.",
        category="models",
        importance=4,
        entities={
            "models": ["Claude 4", "", "Claude 4"],
            "companies": ["Anthropic", " "],
            "techniques": ["LoRA", ""],
            "datasets": [],
        },
        keywords=[" AI ", "", "LoRA", "AI"],
    )
    assert result.entities.models == ["Claude 4"]
    assert result.entities.companies == ["Anthropic"]
    assert result.entities.techniques == ["LoRA"]
    assert result.keywords == ["ai", "lora"]

