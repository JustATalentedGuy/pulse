import re

from pydantic import BaseModel, Field, field_validator


class DigestGenerationResult(BaseModel):
    headline: str = Field(min_length=5, max_length=200)
    narrative: str = Field(min_length=200, max_length=5000)
    key_themes: list[str] = Field(min_length=3, max_length=5)

    @field_validator("headline")
    @classmethod
    def clean_headline(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("narrative")
    @classmethod
    def clean_narrative(cls, value: str) -> str:
        paragraphs = [
            " ".join(paragraph.split())
            for paragraph in re.split(r"\n\s*\n", value.strip())
            if paragraph.strip()
        ]
        if len(paragraphs) != 3:
            sentences = [
                sentence.strip()
                for sentence in re.split(
                    r"(?<=[.!?])\s+",
                    " ".join(value.split()),
                )
                if sentence.strip()
            ]
            if len(sentences) < 3:
                raise ValueError(
                    "Digest narrative must contain at least three sentences"
                )
            base_size, remainder = divmod(len(sentences), 3)
            paragraphs = []
            start = 0
            for index in range(3):
                size = base_size + (1 if index < remainder else 0)
                paragraphs.append(" ".join(sentences[start : start + size]))
                start += size
        return "\n\n".join(paragraphs)

    @field_validator("key_themes")
    @classmethod
    def clean_themes(cls, value: list[str]) -> list[str]:
        themes: list[str] = []
        for item in value:
            cleaned = " ".join(item.split()).strip().lower()
            if cleaned and cleaned not in themes:
                themes.append(cleaned)
        if len(themes) < 3:
            raise ValueError("Digest must contain at least three unique themes")
        return themes[:5]
