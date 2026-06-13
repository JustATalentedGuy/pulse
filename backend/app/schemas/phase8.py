from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrendResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    mention_count: int
    article_ids: list[UUID]
    detected_at: datetime


class PushTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)

    @field_validator("token")
    @classmethod
    def validate_expo_token(cls, value: str) -> str:
        token = value.strip()
        if not (
            token.startswith("ExponentPushToken[")
            or token.startswith("ExpoPushToken[")
        ) or not token.endswith("]"):
            raise ValueError("Token must be a valid Expo push token")
        return token


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=6,
    )


class AskSource(BaseModel):
    id: UUID
    title: str
    url: str
    similarity: float


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource] = Field(default_factory=list)
    used_groq: bool
