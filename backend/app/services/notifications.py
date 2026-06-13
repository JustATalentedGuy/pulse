import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.digest import DailyDigest
from app.models.user_settings import UserSettings


logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
PushSender = Callable[[str, str, str, dict[str, Any]], Awaitable[None]]


async def send_push(
    expo_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            EXPO_PUSH_URL,
            json={
                "to": expo_token,
                "title": title,
                "body": body,
                "data": data or {},
                "priority": "normal",
                "sound": "default",
            },
        )
        response.raise_for_status()


async def _push_token(session: AsyncSession) -> str | None:
    return await session.scalar(
        select(UserSettings.expo_push_token)
        .where(UserSettings.expo_push_token.is_not(None))
        .limit(1)
    )


async def notify_importance_article(
    session: AsyncSession,
    article: Article,
    *,
    sender: PushSender = send_push,
) -> None:
    if article.importance != 5:
        return
    token = await _push_token(session)
    if not token:
        return
    await sender(
        token,
        "High-priority article",
        article.title,
        {
            "type": "article",
            "article_id": str(article.id),
            "url": f"pulse://article/{article.id}",
        },
    )


async def notify_digest_ready(
    session: AsyncSession,
    digest: DailyDigest,
    *,
    sender: PushSender = send_push,
) -> None:
    token = await _push_token(session)
    if not token:
        return
    await sender(
        token,
        "Your daily Pulse digest is ready",
        digest.headline or "The strongest signals are ready to read.",
        {"type": "digest", "url": "pulse://digest"},
    )
