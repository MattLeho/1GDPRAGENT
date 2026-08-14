from __future__ import annotations

from pathlib import Path

import asyncpg

from migrate import migrate


async def schema_signature(connection: asyncpg.Connection) -> tuple[tuple[str, str, str], ...]:
    """Capture schema objects whose drift can change application behaviour."""
    rows = await connection.fetch(
        """
        SELECT object_kind, object_name, definition
        FROM (
            SELECT 'column' AS object_kind,
                   table_name || '.' || column_name AS object_name,
                   concat_ws('|', data_type, udt_name, is_nullable, coalesce(column_default, '')) AS definition
            FROM information_schema.columns
            WHERE table_schema = 'public'
            UNION ALL
            SELECT 'constraint', c.conrelid::regclass::text || '.' || c.conname,
                   pg_get_constraintdef(c.oid, true)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'public'
            UNION ALL
            SELECT 'index', schemaname || '.' || indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            UNION ALL
            SELECT 'view', schemaname || '.' || viewname, definition
            FROM pg_views
            WHERE schemaname = 'public'
            UNION ALL
            SELECT 'function', n.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')',
                   pg_get_functiondef(p.oid)
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p')
            UNION ALL
            SELECT 'trigger', c.relname || '.' || t.tgname, pg_get_triggerdef(t.oid, true)
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND NOT t.tgisinternal
            UNION ALL
            SELECT 'enum', n.nspname || '.' || t.typname,
                   string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE n.nspname = 'public'
            GROUP BY n.nspname, t.typname
        ) AS schema_objects
        ORDER BY object_kind, object_name, definition
        """
    )
    return tuple((row["object_kind"], row["object_name"], row["definition"]) for row in rows)


async def migrate_twice_with_stable_schema(url: str, migrations: Path):
    await migrate(url, migrations)
    connection = await asyncpg.connect(url)
    try:
        first = await schema_signature(connection)
    finally:
        await connection.close()
    await migrate(url, migrations)
    connection = await asyncpg.connect(url)
    try:
        second = await schema_signature(connection)
    finally:
        await connection.close()
    assert second == first
    return first, second
