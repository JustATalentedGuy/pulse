import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.preference import Preference
from app.models.trend import TrendingTopic
from app.models.user_settings import UserSettings


async def main() -> None:
    headers = {"X-API-Key": get_settings().api_key}
    async with SessionLocal() as session:
        settings_count = await session.scalar(
            select(func.count()).select_from(UserSettings)
        )
        trend_count = await session.scalar(
            select(func.count()).select_from(TrendingTopic)
        )
        preference = await session.scalar(select(Preference).limit(1))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=120,
    ) as client:
        trends = await client.get("/trends", headers=headers)
        unrelated = await client.post(
            "/ask",
            json={
                "question": "What is the weather in Mumbai?",
                "conversation_history": [],
            },
            headers=headers,
        )

    checks = [
        ("user settings row exists", settings_count == 1),
        ("trends endpoint is available", trends.status_code == 200),
        (
            "unrelated RAG question avoids Groq",
            unrelated.status_code == 200
            and unrelated.json().get("used_groq") is False,
        ),
        ("preference row exists", preference is not None),
    ]
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
    print(f"Stored trends: {trend_count or 0}")
    if not all(passed for _, passed in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
