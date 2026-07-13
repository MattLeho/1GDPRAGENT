from __future__ import annotations

from uuid import uuid4

import asyncpg
import pytest

from test_task1_database_integration import migrated_database


IMMUTABLE_TABLES = {
    "insight_materialisations",
    "insight_aggregate_buckets",
    "insight_evidence_index",
    "external_context_events",
    "temporal_correlation_candidates",
    "media_location_candidates",
    "insight_catalogue",
}


@pytest.mark.asyncio
async def test_task4_derived_and_evidence_tables_are_database_immutable(migrated_database):
    url, _, _ = migrated_database
    connection = await asyncpg.connect(url)
    try:
        rows = await connection.fetch(
            """SELECT c.relname AS table_name, t.tgname AS trigger_name
               FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               WHERE NOT t.tgisinternal
                 AND c.relname=ANY($1::text[])""",
            list(IMMUTABLE_TABLES),
        )
        triggers = {(row["table_name"], row["trigger_name"]) for row in rows}
        for table_name in IMMUTABLE_TABLES:
            assert (table_name, f"{table_name}_no_update") in triggers
            assert (table_name, f"{table_name}_no_delete") in triggers

        primary_key_columns=await connection.fetch(
            """SELECT a.attname FROM pg_constraint c
               JOIN unnest(c.conkey) WITH ORDINALITY AS key(attnum,ord) ON TRUE
               JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=key.attnum
               WHERE c.conrelid='insight_evidence_index'::regclass AND c.contype='p'
               ORDER BY key.ord"""
        )
        assert [row["attname"] for row in primary_key_columns][0] == "materialisation_id"

        event_id = uuid4()
        await connection.execute(
            """INSERT INTO external_context_events(id,title,event_type,occurred_at)
               VALUES($1,'Original title','fixture',NOW())""",
            event_id,
        )

        transaction = connection.transaction()
        await transaction.start()
        with pytest.raises(asyncpg.RaiseError, match="immutable"):
            await connection.execute(
                "UPDATE external_context_events SET title='Rewritten' WHERE id=$1",
                event_id,
            )
        await transaction.rollback()

        transaction = connection.transaction()
        await transaction.start()
        with pytest.raises(asyncpg.RaiseError, match="immutable"):
            await connection.execute("DELETE FROM external_context_events WHERE id=$1", event_id)
        await transaction.rollback()
    finally:
        await connection.close()
