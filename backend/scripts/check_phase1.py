import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from app.database import SessionLocal


@dataclass(frozen=True)
class Check:
    name: str
    query: str
    expected: object


CHECKS = (
    Check(
        "missing required article fields",
        "SELECT COUNT(*) FROM articles "
        "WHERE title IS NULL OR url IS NULL OR source IS NULL OR raw_text IS NULL",
        0,
    ),
    Check(
        "raw text containing HTML tags",
        "SELECT COUNT(*) FROM articles WHERE raw_text ~ '</?[A-Za-z][^>]*>'",
        0,
    ),
    Check(
        "duplicate content hashes",
        "SELECT COUNT(*) FROM ("
        "SELECT content_hash FROM articles GROUP BY content_hash HAVING COUNT(*) > 1"
        ") duplicates",
        0,
    ),
    Check(
        "articles with invalid enrichment status",
        "SELECT COUNT(*) FROM articles WHERE enrichment_status NOT IN "
        "('pending','processing','done','failed','skipped')",
        0,
    ),
)

REQUIRED_INGESTION_SOURCES = {"rss", "github", "arxiv"}


async def main() -> None:
    failed = False
    async with SessionLocal() as session:
        total = await session.scalar(text("SELECT COUNT(*) FROM articles"))
        print(f"articles total: {total}")
        if total < 50:
            failed = True
            print("FAIL: Phase 2 requires at least 50 articles")

        for check in CHECKS:
            actual = await session.scalar(text(check.query))
            status = "PASS" if actual == check.expected else "FAIL"
            failed = failed or status == "FAIL"
            print(f"{status}: {check.name}: {actual}")

        source_rows = (
            await session.execute(
                text(
                    "SELECT source, COUNT(*) FROM articles "
                    "GROUP BY source ORDER BY COUNT(*) DESC"
                )
            )
        ).all()
        print("article sources:")
        for source, count in source_rows:
            print(f"  {source}: {count}")

        latest_runs = (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (source) source, status, items_fetched, "
                    "items_new, items_deduped, error "
                    "FROM ingestion_runs ORDER BY source, started_at DESC"
                )
            )
        ).all()
        print("latest ingestion runs:")
        observed_sources = {row.source for row in latest_runs}
        for row in latest_runs:
            print(
                f"  {row.source}: {row.status}; fetched={row.items_fetched}; "
                f"new={row.items_new}; deduped={row.items_deduped}; "
                f"error={row.error or '-'}"
            )
            if (
                row.source in REQUIRED_INGESTION_SOURCES
                and (row.status != "done" or row.items_fetched <= 0)
            ):
                failed = True
        missing_sources = REQUIRED_INGESTION_SOURCES - observed_sources
        if missing_sources:
            failed = True
            print(
                "FAIL: missing ingestion runs for: "
                + ", ".join(sorted(missing_sources))
            )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
