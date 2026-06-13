from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.user_settings import UserSettings


async def ensure_user_settings_row() -> None:
    async with SessionLocal() as session:
        settings = await session.scalar(select(UserSettings).limit(1))
        if settings is None:
            session.add(UserSettings())
            await session.commit()


async def store_push_token(
    session: AsyncSession,
    token: str,
) -> UserSettings:
    settings = await session.scalar(
        select(UserSettings).with_for_update().limit(1)
    )
    if settings is None:
        settings = UserSettings()
        session.add(settings)
    settings.expo_push_token = token
    settings.updated_at = datetime.now(UTC)
    await session.commit()
    return settings
