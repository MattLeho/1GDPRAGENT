"""Disposable SETTINGS-002 migration fixtures for 033a, 034 and 036.

Migration 010 seeds a global ``processing_settings`` singleton before any
profile can exist. These fixtures prove that the ordered preflight (033a)
removes only a pristine, ownerless scaffold row, that 034 still assigns a
modified legacy singleton to the only profile and still fails closed when
ownership is ambiguous, and that 036 lets every profile own its own row.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import asyncpg
import pytest

from migrate import migrate
from tests.migration_fixtures.schema_signature import migrate_twice_with_stable_schema


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations"
PRE_SETTINGS_OWNERSHIP_CUTOFF = "033a"
PRISTINE_FILTER = (
    "processing_mode='local_first' AND external_fallback_enabled=false "
    "AND approved_external_engines='[]'::jsonb"
)
SINGLETON_GUARD_SQL = (
    "SELECT EXISTS (SELECT 1 FROM pg_constraint "
    "WHERE conrelid='public.processing_settings'::regclass AND contype='c' "
    r"AND pg_get_constraintdef(oid) ~* '\(\s*id\s*=\s*1\s*\)')"
)


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is required for disposable migration fixtures")
    return value


async def _temporary_database(label: str):
    base_url = _database_url()
    admin = await asyncpg.connect(base_url)
    name = f"r0_settings_{label}_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    return admin, name, f"{base_url.rsplit('/', 1)[0]}/{name}"


async def _drop_database(admin: asyncpg.Connection, name: str) -> None:
    await admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",
        name,
    )
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    await admin.close()


def _version(path: Path) -> str:
    return path.name.split("_", 1)[0]


def _copy_migrations(destination: Path, *, before: str | None = None, exclude: set[str] = frozenset()) -> None:
    for source in sorted(MIGRATIONS.glob("*.sql")):
        version = _version(source)
        if before is not None and version >= before:
            continue
        if version in exclude:
            continue
        (destination / source.name).write_bytes(source.read_bytes())


async def _singleton_guard_present(connection: asyncpg.Connection) -> bool:
    return await connection.fetchval(SINGLETON_GUARD_SQL)


@pytest.mark.asyncio
async def test_clean_install_has_no_ownerless_settings_and_each_profile_owns_one_row():
    admin, name, url = await _temporary_database("clean")
    try:
        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM processing_settings") == 0
            assert await connection.fetchval(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='processing_settings' AND column_name='profile_id'"
            ) == "NO"
            assert await _singleton_guard_present(connection) is False
            first = await connection.fetchval("INSERT INTO profiles(identity_name) VALUES('first') RETURNING id")
            second = await connection.fetchval("INSERT INTO profiles(identity_name) VALUES('second') RETURNING id")
            upsert = (
                "INSERT INTO processing_settings(profile_id,processing_mode,external_fallback_enabled,"
                "approved_external_engines,updated_at) VALUES($1,$2,false,'[]'::jsonb,NOW()) "
                "ON CONFLICT(profile_id) DO UPDATE SET processing_mode=EXCLUDED.processing_mode"
            )
            await connection.execute(upsert, first, "strict_local")
            await connection.execute(upsert, second, "controlled_cloud")
            await connection.execute(upsert, second, "local_first")
            rows = await connection.fetch("SELECT profile_id, processing_mode FROM processing_settings ORDER BY id")
            assert [(row["profile_id"], row["processing_mode"]) for row in rows] == [
                (first, "strict_local"),
                (second, "local_first"),
            ]
            with pytest.raises(asyncpg.exceptions.NotNullViolationError):
                await connection.execute("INSERT INTO processing_settings(processing_mode) VALUES('strict_local')")
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_modified_legacy_singleton_is_assigned_to_the_only_profile():
    admin, name, url = await _temporary_database("single_owner")
    try:
        with tempfile.TemporaryDirectory(prefix="settings-migrations-") as temporary_directory:
            before = Path(temporary_directory)
            _copy_migrations(before, before=PRE_SETTINGS_OWNERSHIP_CUTOFF)
            await migrate(url, before)
            connection = await asyncpg.connect(url)
            try:
                assert await connection.fetchval("SELECT count(*) FROM processing_settings WHERE id=1") == 1
                await connection.execute(
                    "UPDATE processing_settings SET processing_mode='strict_local', external_fallback_enabled=true WHERE id=1"
                )
                profile_id = await connection.fetchval(
                    "INSERT INTO profiles(identity_name) VALUES('only owner') RETURNING id"
                )
            finally:
                await connection.close()
        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            rows = await connection.fetch(
                "SELECT id, profile_id, processing_mode, external_fallback_enabled FROM processing_settings"
            )
            assert [(r["id"], r["profile_id"], r["processing_mode"], r["external_fallback_enabled"]) for r in rows] == [
                (1, profile_id, "strict_local", True)
            ]
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_pristine_legacy_singleton_is_removed_not_assigned_when_ownership_is_ambiguous():
    admin, name, url = await _temporary_database("pristine_ambiguous")
    try:
        with tempfile.TemporaryDirectory(prefix="settings-migrations-") as temporary_directory:
            before = Path(temporary_directory)
            _copy_migrations(before, before=PRE_SETTINGS_OWNERSHIP_CUTOFF)
            await migrate(url, before)
            connection = await asyncpg.connect(url)
            try:
                assert await connection.fetchval(f"SELECT count(*) FROM processing_settings WHERE {PRISTINE_FILTER}") == 1
                await connection.execute("INSERT INTO profiles(identity_name) VALUES('one'),('two')")
            finally:
                await connection.close()
        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM processing_settings") == 0
            assert await connection.fetchval("SELECT count(*) FROM profiles") == 2
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_modified_legacy_singleton_still_fails_closed_when_ownership_is_ambiguous():
    admin, name, url = await _temporary_database("modified_ambiguous")
    try:
        with tempfile.TemporaryDirectory(prefix="settings-migrations-") as temporary_directory:
            before = Path(temporary_directory)
            _copy_migrations(before, before=PRE_SETTINGS_OWNERSHIP_CUTOFF)
            await migrate(url, before)
            connection = await asyncpg.connect(url)
            try:
                await connection.execute("UPDATE processing_settings SET processing_mode='controlled_cloud' WHERE id=1")
                await connection.execute("INSERT INTO profiles(identity_name) VALUES('one'),('two')")
            finally:
                await connection.close()
        with pytest.raises(Exception, match=r"SETTINGS-002 cannot infer canonical ownership for 1 row\(s\) in processing_settings"):
            await migrate(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            # The failed transaction left the modified configuration intact and unowned.
            assert await connection.fetchval("SELECT processing_mode FROM processing_settings WHERE id=1") == "controlled_cloud"
            assert await connection.fetchval("SELECT count(*) FROM gdpr_schema_migrations WHERE version='034'") == 0
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_repair_migrations_are_safe_on_an_installation_where_034_already_ran():
    """Installations that applied 034 before 033a existed gain 033a and 036 without touching owned rows."""
    admin, name, url = await _temporary_database("post_034")
    try:
        with tempfile.TemporaryDirectory(prefix="settings-migrations-") as temporary_directory:
            pre_034 = Path(temporary_directory) / "pre_034"
            pre_034.mkdir()
            _copy_migrations(pre_034, before="034", exclude={"033a"})
            await migrate(url, pre_034)
            connection = await asyncpg.connect(url)
            try:
                owner = await connection.fetchval("INSERT INTO profiles(identity_name) VALUES('owner') RETURNING id")
            finally:
                await connection.close()
            # 034 without the preflight succeeds here only because the scaffold row can be owned.
            without_repair = Path(temporary_directory) / "without_repair"
            without_repair.mkdir()
            _copy_migrations(without_repair, exclude={"033a", "036"})
            await migrate(url, without_repair)
            connection = await asyncpg.connect(url)
            try:
                assert await connection.fetchval("SELECT profile_id FROM processing_settings WHERE id=1") == owner
                assert await _singleton_guard_present(connection) is True
            finally:
                await connection.close()
        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT profile_id FROM processing_settings WHERE id=1") == owner
            assert await _singleton_guard_present(connection) is False
            assert await connection.fetchval("SELECT count(*) FROM gdpr_schema_migrations") == len(list(MIGRATIONS.glob("*.sql")))
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)
