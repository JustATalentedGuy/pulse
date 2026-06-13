import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.article import Article
from app.models.digest import DailyDigest


async def main() -> None:
    failed = False
    headers = {"X-API-Key": get_settings().api_key}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        feed = await client.get("/feed", headers=headers, params={"limit": 10})
        bookmarks = await client.get("/bookmarks", headers=headers)
        digest_history = await client.get("/digest/history", headers=headers)

    checks = [
        ("feed remains available", feed.status_code == 200),
        ("bookmarks endpoint is available", bookmarks.status_code == 200),
        ("digest history endpoint is available", digest_history.status_code == 200),
    ]
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {label}")
        failed = failed or not passed

    async with SessionLocal() as session:
        bookmarked = await session.scalar(
            select(func.count())
            .select_from(Article)
            .where(Article.bookmarked.is_(True))
        )
        digests = await session.scalar(select(func.count()).select_from(DailyDigest))
    print(f"Bookmarked articles: {bookmarked or 0}")
    print(f"Stored daily digests: {digests or 0}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
