import asyncio

from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal


async def main() -> None:
    failed = False
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("GMAIL_CLIENT_ID", settings.gmail_client_id),
            ("GMAIL_CLIENT_SECRET", settings.gmail_client_secret),
            ("GMAIL_REFRESH_TOKEN", settings.gmail_refresh_token),
            ("NEWSLETTER_SENDERS", settings.newsletter_senders),
        )
        if not value
    ]
    if missing:
        failed = True
        print("FAIL: missing Gmail configuration: " + ", ".join(missing))
    else:
        print("PASS: Gmail OAuth and sender configuration is present")

    async with SessionLocal() as session:
        latest_run = (
            await session.execute(
                text(
                    "SELECT status, items_fetched, items_new, items_deduped, error "
                    "FROM ingestion_runs WHERE source = 'gmail' "
                    "ORDER BY started_at DESC LIMIT 1"
                )
            )
        ).one_or_none()
        if latest_run is None:
            failed = True
            print("FAIL: no Gmail ingestion run has been recorded")
        else:
            print(
                "latest Gmail run: "
                f"{latest_run.status}; fetched={latest_run.items_fetched}; "
                f"new={latest_run.items_new}; "
                f"deduped={latest_run.items_deduped}; "
                f"error={latest_run.error or '-'}"
            )
            if latest_run.status != "done":
                failed = True
                print("FAIL: latest Gmail ingestion run did not complete")

        article_count = await session.scalar(
            text("SELECT COUNT(*) FROM articles WHERE source = 'gmail'")
        )
        print(f"Gmail articles: {article_count}")
        if article_count == 0:
            failed = True
            print("FAIL: no Gmail articles have been stored")

        duplicate_source_ids = await session.scalar(
            text(
                "SELECT COUNT(*) FROM ("
                "SELECT source_id FROM articles "
                "WHERE source = 'gmail' AND source_id IS NOT NULL "
                "GROUP BY source_id HAVING COUNT(*) > 1"
                ") duplicates"
            )
        )
        status = "PASS" if duplicate_source_ids == 0 else "FAIL"
        print(f"{status}: duplicate Gmail source IDs: {duplicate_source_ids}")
        failed = failed or duplicate_source_ids != 0

        html_rows = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE source = 'gmail' "
                "AND raw_text ~ '</?[A-Za-z][^>]*>'"
            )
        )
        status = "PASS" if html_rows == 0 else "FAIL"
        print(f"{status}: Gmail raw text containing HTML: {html_rows}")
        failed = failed or html_rows != 0

        promotional_rows = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE source = 'gmail' AND ("
                "raw_text ~* '\\m(advertisement|brought to you by|"
                "manage preferences|paid partnership|sponsored|"
                "unsubscribe)\\M' "
                "OR title ~* '^(advertisement|promotion|sponsored)[: -]')"
            )
        )
        status = "PASS" if promotional_rows == 0 else "FAIL"
        print(
            f"{status}: Gmail articles with promotional/footer leakage: "
            f"{promotional_rows}"
        )
        failed = failed or promotional_rows != 0

        weak_rows = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE source = 'gmail' AND ("
                "length(btrim(raw_text)) < 50 "
                "OR length(btrim(title)) < 4 "
                "OR url !~* '^https?://')"
            )
        )
        status = "PASS" if weak_rows == 0 else "FAIL"
        print(f"{status}: weak Gmail article records: {weak_rows}")
        failed = failed or weak_rows != 0

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
