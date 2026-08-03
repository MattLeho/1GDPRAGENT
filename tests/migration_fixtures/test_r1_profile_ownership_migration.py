from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import asyncpg
import pytest

from migrate import migrate


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations"


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is required for disposable migration fixtures")
    return value


async def _temporary_database(label: str):
    base_url = _database_url()
    admin = await asyncpg.connect(base_url)
    name = f"r1_{label}_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    return admin, name, f"{base_url.rsplit('/', 1)[0]}/{name}"


async def _drop_database(admin: asyncpg.Connection, name: str) -> None:
    await admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1", name)
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    await admin.close()


@pytest.mark.asyncio
async def test_r1_profile_roots_are_non_null_and_indexed_on_clean_install():
    admin, name, url = await _temporary_database("clean_ownership")
    try:
        await migrate(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            for table in (
                "requests", "received_data", "request_threads", "vendor_lists", "id_documents",
                "connector_credentials", "email_settings",
            ):
                assert await connection.fetchval(
                    "SELECT is_nullable='NO' FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=$1 AND column_name='profile_id'",
                    table,
                ) is True
            columns = await connection.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='access_requests'"
            )
            assert "profile_id" in {row["column_name"] for row in columns}
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_r1_upgrade_fails_closed_for_ambiguous_unowned_personal_data():
    admin, name, url = await _temporary_database("ambiguous_ownership")
    try:
        with tempfile.TemporaryDirectory(prefix="r1-migrations-") as temporary_directory:
            migrations_before_r1 = Path(temporary_directory)
            for source in sorted(MIGRATIONS.glob("*.sql")):
                if source.name < "030_r1_profile_ownership.sql":
                    (migrations_before_r1 / source.name).write_bytes(source.read_bytes())
            await migrate(url, migrations_before_r1)
            connection = await asyncpg.connect(url)
            try:
                await connection.execute("INSERT INTO profiles(identity_name) VALUES('one'),('two')")
                await connection.execute("INSERT INTO requests(company_name) VALUES('ambiguous legacy request')")
            finally:
                await connection.close()

            with pytest.raises(Exception, match="cannot infer canonical ownership"):
                await migrate(url, MIGRATIONS)
    finally:
        await _drop_database(admin, name)
