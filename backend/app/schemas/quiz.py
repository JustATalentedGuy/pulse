from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


AnswerKey = Literal["A", "B", "C", "D"]
EXPECTED_OPTIONS = {"A", "B", "C", "D"}


class QuizQuestion(BaseModel):
    id: int = Field(ge=1, le=3)
    question: str = Field(min_length=5, max_length=500)
    options: dict[AnswerKey, str]
    correct: AnswerKey
    explanation: str = Field(min_length=5, max_length=1000)

    @field_validator("question", "explanation")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Quiz text cannot be empty")
        return cleaned

    @field_validator("options")
    @classmethod
    def validate_options(
        cls,
        value: dict[AnswerKey, str],
    ) -> dict[AnswerKey, str]:
        if set(value) != EXPECTED_OPTIONS:
            raise ValueError("Quiz options must contain exactly A, B, C, and D")
        cleaned = {key: " ".join(text.split()) for key, text in value.items()}
        if any(not text for text in cleaned.values()):
            raise ValueError("Quiz option text cannot be empty")
        return cleaned


class QuizGenerationResponse(BaseModel):
    article_id: UUID
    article_title: str
    questions: list[QuizQuestion] = Field(min_length=3, max_length=3)


class QuizAnswer(BaseModel):
    question_id: int = Field(ge=1, le=3)
    selected: AnswerKey


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=3, max_length=3)
    duration_seconds: int = Field(ge=1, le=7200)

    @field_validator("answers")
    @classmethod
    def validate_answer_ids(cls, value: list[QuizAnswer]) -> list[QuizAnswer]:
        if {answer.question_id for answer in value} != {1, 2, 3}:
            raise ValueError("Answers must cover question IDs 1, 2, and 3")
        return value


class QuizAnswerResult(BaseModel):
    question_id: int
    correct: bool
    feedback: str
    explanation: str


class QuizSubmitResponse(BaseModel):
    score: float
    correct_count: int
    total_questions: int
    results: list[QuizAnswerResult]
