import asyncio

from sqlalchemy import text

from app.database import SessionLocal


async def main() -> None:
    failed = False
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT enrichment_status, COUNT(*) "
                    "FROM articles GROUP BY enrichment_status "
                    "ORDER BY enrichment_status"
                )
            )
        ).all()
        print("enrichment states:")
        for status, count in rows:
            print(f"  {status}: {count}")

        enriched = await session.scalar(
            text("SELECT COUNT(*) FROM articles WHERE enrichment_status = 'done'")
        )
        if enriched < 10:
            failed = True
            print("FAIL: Phase 3 requires at least 10 enriched articles")

        invalid = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'done' AND ("
                "summary IS NULL OR category IS NULL OR importance IS NULL "
                "OR entities IS NULL OR keywords IS NULL OR embedding IS NULL "
                "OR enriched_at IS NULL)"
            )
        )
        print(f"{'PASS' if invalid == 0 else 'FAIL'}: incomplete enrichments: {invalid}")
        failed = failed or invalid != 0

        invalid_categories = (
            await session.execute(
                text(
                    "SELECT DISTINCT category FROM articles "
                    "WHERE enrichment_status = 'done' "
                    "AND category NOT IN "
                    "('models','research','tools','cloud','industry','other')"
                )
            )
        ).all()
        print(
            f"{'PASS' if not invalid_categories else 'FAIL'}: invalid categories: "
            f"{len(invalid_categories)}"
        )
        failed = failed or bool(invalid_categories)

        missing_embeddings = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'done' AND embedding IS NULL"
            )
        )
        print(
            f"{'PASS' if missing_embeddings == 0 else 'FAIL'}: "
            f"missing embeddings: {missing_embeddings}"
        )
        failed = failed or missing_embeddings != 0

        invalid_dimensions = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'done' "
                "AND vector_dims(embedding) != 384"
            )
        )
        print(
            f"{'PASS' if invalid_dimensions == 0 else 'FAIL'}: "
            f"invalid embedding dimensions: {invalid_dimensions}"
        )
        failed = failed or invalid_dimensions != 0

        invalid_values = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'done' AND ("
                "length(summary) NOT BETWEEN 10 AND 1000 "
                "OR importance NOT BETWEEN 1 AND 5 "
                "OR summary ~ '<[A-Za-z/][^>]*>')"
            )
        )
        print(
            f"{'PASS' if invalid_values == 0 else 'FAIL'}: "
            f"invalid summary or importance values: {invalid_values}"
        )
        failed = failed or invalid_values != 0

        invalid_entity_maps = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'done' AND ("
                "NOT entities ?& ARRAY['models','companies','techniques','datasets'] "
                "OR EXISTS ("
                "SELECT 1 FROM jsonb_object_keys(entities) AS entity_key "
                "WHERE entity_key NOT IN "
                "('models','companies','techniques','datasets'))"
                ")"
            )
        )
        print(
            f"{'PASS' if invalid_entity_maps == 0 else 'FAIL'}: "
            f"invalid entity maps: {invalid_entity_maps}"
        )
        failed = failed or invalid_entity_maps != 0

        empty_entities = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles a "
                "WHERE a.enrichment_status = 'done' AND EXISTS ("
                "SELECT 1 FROM jsonb_each(a.entities) AS entity_group "
                "CROSS JOIN LATERAL "
                "jsonb_array_elements_text(entity_group.value) AS entity(value) "
                "WHERE btrim(entity.value) = '')"
            )
        )
        print(
            f"{'PASS' if empty_entities == 0 else 'FAIL'}: "
            f"empty entity values: {empty_entities}"
        )
        failed = failed or empty_entities != 0

        processing = await session.scalar(
            text(
                "SELECT COUNT(*) FROM articles "
                "WHERE enrichment_status = 'processing'"
            )
        )
        print(
            f"{'PASS' if processing == 0 else 'FAIL'}: "
            f"articles stuck processing: {processing}"
        )
        failed = failed or processing != 0

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
