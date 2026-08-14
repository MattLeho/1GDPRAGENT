"""Disposable R2 request-lifecycle migration fixtures."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import pytest

from migrate import migrate
from tests.migration_fixtures.schema_signature import migrate_twice_with_stable_schema


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations"
R2_MIGRATION = MIGRATIONS / "031_r2_request_lifecycle.sql"
R2_PREFLIGHT = MIGRATIONS / "030a_r2_legacy_request_preflight.sql"


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is required for disposable migration fixtures")
    return value


async def _temporary_database(label: str):
    base_url = _database_url()
    admin = await asyncpg.connect(base_url)
    name = f"r2_{label}_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    return admin, name, f"{base_url.rsplit('/', 1)[0]}/{name}"


async def _drop_database(admin: asyncpg.Connection, name: str) -> None:
    await admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1", name)
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    await admin.close()


def _migrations_before_r2(directory: Path) -> None:
    for source in sorted(MIGRATIONS.glob("*.sql")):
        if source.name < R2_MIGRATION.name:
            (directory / source.name).write_bytes(source.read_bytes())


@pytest.mark.asyncio
async def test_r2_clean_install_runner_and_sql_are_idempotent():
    admin, name, url = await _temporary_database("clean")
    try:
        # Replay the historical migration at its own schema point. Later
        # migrations deliberately extend objects that 031 created.
        with tempfile.TemporaryDirectory(prefix="r2-through-031-") as temporary:
            through_r2 = Path(temporary)
            for source in sorted(MIGRATIONS.glob("*.sql")):
                if source.name <= R2_MIGRATION.name:
                    (through_r2 / source.name).write_bytes(source.read_bytes())
            await migrate(url, through_r2)
        connection = await asyncpg.connect(url)
        try:
            await connection.execute(R2_MIGRATION.read_text(encoding="utf-8"))
        finally:
            await connection.close()

        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            columns = {
                row["column_name"]: row
                for row in await connection.fetch(
                    "SELECT column_name,data_type,is_nullable,column_default "
                    "FROM information_schema.columns WHERE table_schema='public' AND table_name='requests'"
                )
            }
            expected = {
                "updated_at", "sent_at", "controller_received_at", "identity_requested_at",
                "identity_verified_at", "clarification_requested_at", "clarification_resolved_at",
                "response_received_at", "completed_at", "deadline_at", "deadline_basis",
                "extension_notified_at", "extension_deadline_at", "next_action_at",
                "extension_reason",
            }
            assert expected <= set(columns)
            assert columns["updated_at"]["is_nullable"] == "NO"
            assert "now()" in columns["updated_at"]["column_default"].lower()
            assert all(
                columns[name]["data_type"] == "timestamp with time zone"
                for name in expected - {"deadline_basis", "extension_reason"}
            )
            assert await connection.fetchval(
                "SELECT count(*) FROM gdpr_schema_migrations WHERE version='031'"
            ) == 1

            assert await connection.fetchval(
                "SELECT count(*) FROM pg_trigger WHERE tgrelid='requests'::regclass "
                "AND tgname IN ('requests_set_updated_at','requests_status_transition_guard') AND NOT tgisinternal"
            ) == 2
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_r2_upgrade_preserves_rows_and_does_not_fabricate_legal_dates():
    admin, name, url = await _temporary_database("legacy")
    try:
        with tempfile.TemporaryDirectory(prefix="r2-migrations-") as temporary_directory:
            before_r2 = Path(temporary_directory)
            _migrations_before_r2(before_r2)
            await migrate(url, before_r2)

        connection = await asyncpg.connect(url)
        try:
            profile_id = await connection.fetchval(
                "INSERT INTO profiles(identity_name) VALUES('R2 legacy profile') RETURNING id"
            )
            created_at = datetime(2024, 1, 31, 9, 0, tzinfo=timezone.utc)
            legacy_deadline = datetime(2024, 3, 1, 9, 0, tzinfo=timezone.utc)
            legacy_next_action = datetime(2024, 2, 7, 9, 0, tzinfo=timezone.utc)
            request_id = await connection.fetchval(
                "INSERT INTO requests(company_name,status,created_at,deadline_date,next_action_date,profile_id) "
                "VALUES('Legacy controller','completed',$1,$2,$3,$4) RETURNING id",
                created_at, legacy_deadline, legacy_next_action, profile_id,
            )
            await connection.execute(
                "INSERT INTO request_chat_messages(request_id,sender,message) VALUES($1,'user','legacy chat')",
                request_id,
            )
            await connection.execute(
                "INSERT INTO received_data(request_id,file_name,profile_id) VALUES($1,'legacy.json',$2)",
                request_id, profile_id,
            )
            await connection.execute(
                "INSERT INTO messages(request_id,sender,content) VALUES($1,'company','legacy response')",
                request_id,
            )
            await connection.execute(
                "INSERT INTO workflow_logs(request_id,workflow_name,status) VALUES($1,'legacy-flow','completed')",
                request_id,
            )
            event_id = await connection.fetchval(
                "INSERT INTO request_events(request_id,event_type,event_description,event_date) "
                "VALUES($1,'legacy','legacy event',$2) RETURNING id",
                request_id, created_at,
            )
            legacy_status_ids = {}
            for legacy_status in (
                "draft_pending_review", "pending", "verification_needed", "data_available",
                "data_received", "partial_data", "processing", "data_analyzed", "rejected",
                "extended", "action_required", "unknown_vendor_state",
            ):
                legacy_status_ids[legacy_status] = await connection.fetchval(
                    "INSERT INTO requests(company_name,status,profile_id) VALUES($1,$2,$3) RETURNING id",
                    f"Legacy {legacy_status}", legacy_status, profile_id,
                )
        finally:
            await connection.close()

        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            row = await connection.fetchrow("SELECT * FROM requests WHERE id=$1", request_id)
            assert row["created_at"] == created_at
            assert row["updated_at"] is not None
            assert row["deadline_date"] == legacy_deadline
            assert row["next_action_date"] == legacy_next_action
            assert row["next_action_at"] == legacy_next_action
            for field in (
                "sent_at", "controller_received_at", "identity_requested_at", "identity_verified_at",
                "clarification_requested_at", "clarification_resolved_at", "response_received_at",
                "completed_at", "deadline_at", "extension_notified_at", "extension_deadline_at",
            ):
                assert row[field] is None
            assert row["deadline_basis"] is None

            assert await connection.fetchval(
                "SELECT count(*) FROM request_chat_messages WHERE request_id=$1 AND message='legacy chat'",
                request_id,
            ) == 1
            assert await connection.fetchval("SELECT count(*) FROM received_data WHERE request_id=$1", request_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM messages WHERE request_id=$1", request_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM workflow_logs WHERE request_id=$1", request_id) == 1
            event = await connection.fetchrow("SELECT * FROM request_events WHERE id=$1", event_id)
            assert event["actor"] == "legacy/unknown"
            assert event["reason"] == "legacy/unknown"
            assert event["previous_state"] is None and event["next_state"] is None
            expected_statuses = {
                "draft_pending_review": "ready_for_review", "pending": "awaiting_response",
                "verification_needed": "identity_action_required", "data_available": "response_received",
                "data_received": "response_received", "partial_data": "response_received",
                "processing": "processing_response", "data_analyzed": "processing_response",
                "rejected": "closed_incomplete", "extended": "awaiting_response",
                "action_required": "ready_for_review", "unknown_vendor_state": "ready_for_review",
            }
            for legacy_status, mapped in expected_statuses.items():
                legacy_id = legacy_status_ids[legacy_status]
                assert await connection.fetchval("SELECT status FROM requests WHERE id=$1", legacy_id) == mapped
                audit = await connection.fetchrow(
                    "SELECT previous_state,next_state,actor,evidence_reference FROM request_events WHERE request_id=$1",
                    legacy_id,
                )
                assert dict(audit) == {"previous_state": legacy_status, "next_state": mapped,
                    "actor": "migration:032", "evidence_reference": "migration:032"}
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_r2_preflight_upgrades_a_minimal_historical_requests_table():
    admin, name, url = await _temporary_database("minimal")
    try:
        connection = await asyncpg.connect(url)
        try:
            await connection.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
            await connection.execute(
                "CREATE TABLE requests("
                "id uuid primary key default gen_random_uuid(), company_name text not null, "
                "company_url text, domain text, status text default 'draft', "
                "request_type text default 'access', created_at timestamptz default now())"
            )
            await connection.execute(
                "CREATE TABLE profiles("
                "id uuid primary key default gen_random_uuid(), identity_name text not null, "
                "encrypted_name text, encrypted_email text, encrypted_address text, "
                "created_at timestamptz not null default now())"
            )
            await connection.execute(
                "INSERT INTO profiles(identity_name) VALUES('Minimal legacy owner')"
            )
            request_id = await connection.fetchval(
                "INSERT INTO requests(company_name,status) VALUES('Minimal legacy controller','draft') RETURNING id"
            )
        finally:
            await connection.close()

        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval(
                "SELECT count(*) FROM requests WHERE id=$1 AND company_name='Minimal legacy controller'",
                request_id,
            ) == 1
            for column in (
                "next_action_date", "deadline_date", "data_volume_mb",
                "data_period_start", "data_period_end", "progress", "notes",
                "next_action_at", "deadline_at", "updated_at",
            ):
                assert await connection.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='requests' AND column_name=$1)",
                    column,
                )
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_r2_view_guards_transitions_events_and_updated_at():
    admin, name, url = await _temporary_database("guards")
    try:
        await migrate_twice_with_stable_schema(url, MIGRATIONS)
        connection = await asyncpg.connect(url)
        try:
            profile_id = await connection.fetchval(
                "INSERT INTO profiles(identity_name) VALUES('R2 transition profile') RETURNING id"
            )
            request_id = await connection.fetchval(
                "INSERT INTO requests(company_name,status,profile_id) VALUES('Transition controller','draft',$1) RETURNING id",
                profile_id,
            )
            other_profile_id = await connection.fetchval(
                "INSERT INTO profiles(identity_name) VALUES('R2 other profile') RETURNING id"
            )
            assert await connection.fetchval(
                "SELECT company_name FROM access_requests WHERE id=$1 AND profile_id=$2",
                request_id, profile_id,
            ) == "Transition controller"
            for statement in (
                "INSERT INTO access_requests(id,company_name,profile_id) VALUES(gen_random_uuid(),'blocked',$1)",
                "UPDATE access_requests SET notes='blocked' WHERE id=$1",
                "DELETE FROM access_requests WHERE id=$1",
            ):
                with pytest.raises(asyncpg.PostgresError, match="read-only compatibility view"):
                    async with connection.transaction():
                        await connection.execute(statement, profile_id if "INSERT" in statement else request_id)

            with pytest.raises(asyncpg.PostgresError, match="only be changed by transition_request_state"):
                async with connection.transaction():
                    await connection.execute("UPDATE requests SET status='completed' WHERE id=$1", request_id)

            with pytest.raises(asyncpg.PostgresError, match="invalid request transition"):
                async with connection.transaction():
                    await connection.fetchval(
                        "SELECT (transition_request_state($1,$2,'completed','fixture','invalid jump')).id",
                        request_id, profile_id,
                    )

            # Rejected transitions are atomic: neither state nor audit history changes.
            assert await connection.fetchval("SELECT status FROM requests WHERE id=$1", request_id) == "draft"
            assert await connection.fetchval(
                "SELECT count(*) FROM request_events WHERE request_id=$1", request_id
            ) == 0

            with pytest.raises(asyncpg.PostgresError, match="request not found for canonical profile"):
                async with connection.transaction():
                    await connection.fetchval(
                        "SELECT (transition_request_state($1,$2,'ready_for_review','fixture','wrong owner')).id",
                        request_id, other_profile_id,
                    )
            assert await connection.fetchval("SELECT status FROM requests WHERE id=$1", request_id) == "draft"
            assert await connection.fetchval(
                "SELECT count(*) FROM request_events WHERE request_id=$1", request_id
            ) == 0

            transitioned_at = datetime(2026, 7, 18, 12, 30, tzinfo=timezone.utc)
            next_action_at = transitioned_at + timedelta(days=2)
            row = await connection.fetchrow(
                "SELECT transitioned.* FROM transition_request_state(" 
                "p_request_id => $1, p_profile_id => $2, p_next_state => 'ready_for_review', "
                "p_actor => 'fixture-user', p_reason => 'draft reviewed', "
                "p_evidence_reference => 'evidence:fixture', p_transitioned_at => $3, "
                "p_next_action_at => $4) AS transitioned",
                request_id, profile_id, transitioned_at, next_action_at,
            )
            assert row["status"] == "ready_for_review"
            assert row["next_action_at"] == next_action_at
            assert row["sent_at"] is None and row["deadline_at"] is None

            event = await connection.fetchrow(
                "SELECT * FROM request_events WHERE request_id=$1 AND event_type='state_transition'",
                request_id,
            )
            assert event["actor"] == "fixture-user"
            assert event["previous_state"] == "draft"
            assert event["next_state"] == "ready_for_review"
            assert event["event_date"] == transitioned_at
            assert event["reason"] == "draft reviewed"
            assert event["evidence_reference"] == "evidence:fixture"

            for statement in (
                "UPDATE request_events SET reason='tampered' WHERE id=$1",
                "DELETE FROM request_events WHERE id=$1",
            ):
                with pytest.raises(asyncpg.PostgresError, match="append-only"):
                    async with connection.transaction():
                        await connection.execute(statement, event["id"])

            before = await connection.fetchval("SELECT updated_at FROM requests WHERE id=$1", request_id)
            await connection.execute("SELECT pg_sleep(0.01)")
            await connection.execute("UPDATE requests SET notes='operational update' WHERE id=$1", request_id)
            after = await connection.fetchval("SELECT updated_at FROM requests WHERE id=$1", request_id)
            assert after > before

            with pytest.raises(asyncpg.CheckViolationError):
                await connection.execute(
                    "INSERT INTO requests(company_name,status,profile_id) VALUES('Legacy blocked','processing',$1)",
                    profile_id,
                )
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)
