"""Disposable R0 migration fixtures; no application database is modified."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import asyncpg
import pytest

from migrate import migrate
from tests.migration_fixtures.schema_signature import migrate_twice_with_stable_schema


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
    name = f"r0_{label}_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    return admin, name, f"{base_url.rsplit('/', 1)[0]}/{name}"


async def _drop_database(admin: asyncpg.Connection, name: str) -> None:
    await admin.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",
        name,
    )
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    await admin.close()


async def _apply_twice(url: str):
    return await migrate_twice_with_stable_schema(url, MIGRATIONS)


async def _seed_pre_task1(url: str) -> dict[str, object]:
    connection = await asyncpg.connect(url)
    try:
        await connection.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await connection.execute(
            "CREATE TABLE requests(id uuid primary key default gen_random_uuid(), "
            "company_name text not null, company_url text, domain text, status text default 'draft', "
            "request_type text default 'access', progress integer default 0, data_volume_mb numeric default 0, "
            "next_action_date timestamptz, deadline_date timestamptz, data_period_start timestamptz, "
            "data_period_end timestamptz, notes text, created_at timestamptz default now())"
        )
        await connection.execute(
            "CREATE TABLE received_data(id uuid primary key default gen_random_uuid(), "
            "request_id uuid references requests(id), file_name text not null, "
            "graph_ingested boolean default false, date_received timestamptz default now())"
        )
        await connection.execute(
            "CREATE TABLE data_artifacts(id uuid primary key default gen_random_uuid(), "
            "request_id uuid references requests(id), file_id uuid references received_data(id), "
            "artifact_type text not null, title text not null, payload jsonb not null default '{}'::jsonb, "
            "confidence numeric default 1, source_span text, created_at timestamptz default now(), updated_at timestamptz default now())"
        )
        await connection.execute(
            "CREATE TABLE request_chat_messages(id serial primary key, request_id uuid references requests(id), "
            "role varchar(20) not null, content text not null, timestamp timestamptz default now())"
        )
        await connection.execute(
            "CREATE TABLE user_profiles(id serial primary key, username varchar(255) unique not null, "
            "email varchar(255), password_hash text, profile_picture_url text, "
            "created_at timestamptz default now(), updated_at timestamptz default now())"
        )
        await connection.execute(
            "CREATE TABLE n8n_webhooks(id serial primary key, webhook_name varchar(100) unique not null, "
            "webhook_url text not null, is_active boolean default true, created_at timestamptz default now(), "
            "updated_at timestamptz default now())"
        )
        request_id = await connection.fetchval(
            "INSERT INTO requests(company_name) VALUES('R0 legacy controller') RETURNING id"
        )
        file_id = await connection.fetchval(
            "INSERT INTO received_data(request_id,file_name) VALUES($1,'r0.json') RETURNING id",
            request_id,
        )
        await connection.execute(
            "INSERT INTO data_artifacts(request_id,file_id,artifact_type,title,payload) "
            "VALUES($1,$2,'metric','R0 legacy artifact','{}')",
            request_id,
            file_id,
        )
        await connection.execute(
            "INSERT INTO request_chat_messages(request_id,role,content) VALUES($1,'user','legacy chat')",
            request_id,
        )
        profile_id = await connection.fetchval(
            "INSERT INTO user_profiles(username,email,password_hash,profile_picture_url) "
            "VALUES('r0-legacy','r0@example.invalid','fixture-hash','/r0.png') RETURNING id"
        )
        return {"request_id": request_id, "file_id": file_id, "profile_id": profile_id}
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_clean_schema_applies_twice_and_has_complete_history():
    admin, name, url = await _temporary_database("clean")
    try:
        first_schema, second_schema = await _apply_twice(url)
        assert second_schema == first_schema
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM gdpr_schema_migrations") == len(list(MIGRATIONS.glob("*.sql")))
            assert await connection.fetchval("SELECT to_regclass('public.requests')") == "requests"
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_pre_task1_upgrade_applies_twice_and_preserves_rows():
    admin, name, url = await _temporary_database("pre_task1")
    try:
        seeded = await _seed_pre_task1(url)
        await _apply_twice(url)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM requests WHERE id=$1", seeded["request_id"]) == 1
            assert await connection.fetchval(
                "SELECT r.profile_id=up.default_profile_id FROM requests r CROSS JOIN user_profiles up "
                "WHERE r.id=$1 AND up.legacy_integer_id=$2",
                seeded["request_id"], seeded["profile_id"],
            ) is True
            assert await connection.fetchval("SELECT count(*) FROM received_data WHERE id=$1", seeded["file_id"]) == 1
            assert await connection.fetchval("SELECT count(*) FROM request_chat_messages WHERE request_id=$1 AND sender='user' AND message='legacy chat'", seeded["request_id"]) == 1
            assert await connection.fetchval("SELECT count(*) FROM user_profiles WHERE legacy_integer_id=$1", seeded["profile_id"]) == 1
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_integer_profile_upgrade_preserves_documents_and_backfills_profile():
    admin, name, url = await _temporary_database("integer_profile")
    try:
        connection = await asyncpg.connect(url)
        try:
            await connection.execute(
                "CREATE TABLE user_profiles(id serial primary key, username varchar(255) unique not null, "
                "email varchar(255), password_hash text, avatar_url text, profile_picture_url text, "
                "created_at timestamptz default now(), updated_at timestamptz default now())"
            )
            await connection.execute(
                "CREATE TABLE user_documents(id uuid primary key default gen_random_uuid(), user_id integer references user_profiles(id), "
                "file_name text not null, file_path text not null, file_type text, file_size bigint, created_at timestamptz default now())"
            )
            legacy_id = await connection.fetchval(
                "INSERT INTO user_profiles(username,email,password_hash,avatar_url) VALUES('integer-user','integer@example.invalid','hash','/avatar.png') RETURNING id"
            )
            await connection.execute(
                "INSERT INTO user_documents(user_id,file_name,file_path) VALUES($1,'identity.pdf','fixture://identity.pdf')",
                legacy_id,
            )
        finally:
            await connection.close()
        await _apply_twice(url)
        connection = await asyncpg.connect(url)
        try:
            profile_id = await connection.fetchval("SELECT id FROM user_profiles WHERE legacy_integer_id=$1", legacy_id)
            assert profile_id is not None
            assert await connection.fetchval("SELECT count(*) FROM user_documents WHERE user_id=$1 AND file_path='fixture://identity.pdf'", profile_id) == 1
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_current_representative_state_survives_idempotent_migrate():
    admin, name, url = await _temporary_database("current")
    try:
        await _apply_twice(url)
        connection = await asyncpg.connect(url)
        try:
            profile_id = await connection.fetchval("INSERT INTO profiles(identity_name) VALUES('R0 current profile') RETURNING id")
            request_id = await connection.fetchval(
                "INSERT INTO requests(company_name,profile_id) VALUES('R0 current controller',$1) RETURNING id",
                profile_id,
            )
            await connection.execute("INSERT INTO request_chat_messages(request_id,sender,message) VALUES($1,'user','current chat')", request_id)
            run_id = await connection.fetchval(
                "INSERT INTO analysis_runs(run_type,profile_id,request_id,status,pipeline_version) VALUES('r0-fixture',$1,$2,'completed','r0') RETURNING id",
                profile_id, request_id,
            )
            snapshot_id = await connection.fetchval(
                "INSERT INTO export_snapshots(profile_id,request_id,source_type,analysis_run_id) VALUES($1,$2,'manual_import',$3) RETURNING id",
                profile_id, request_id, run_id,
            )
            digest = hashlib.sha256(b"r0-fixture").hexdigest()
            blob_id = await connection.fetchval(
                "INSERT INTO content_blobs(sha256,byte_size,storage_uri) VALUES($1,10,'fixture://r0') RETURNING id", digest
            )
            artifact_id = await connection.fetchval(
                "INSERT INTO source_artifacts(export_snapshot_id,content_blob_id,original_path,file_name) VALUES($1,$2,'r0.json','r0.json') RETURNING id",
                snapshot_id, blob_id,
            )
            locator_id = await connection.fetchval(
                "INSERT INTO evidence_locators(artifact_id,locator_type,locator,raw_hash,verified) VALUES($1,'text_span','{\"byte_start\":0,\"byte_end\":1}',$2,true) RETURNING id",
                artifact_id, hashlib.sha256(b"x").hexdigest(),
            )
            assertion_id = await connection.fetchval(
                "INSERT INTO assertions(subject_type,subject_ref,predicate,object_type,object_ref,assertion_type,data_class,status,epistemic_basis,ingested_at,derivation_method,derivation_version,analysis_run_id) "
                "VALUES('Profile',$1,'HAS_GRAPH_REFERENCE','node_ref','GraphNode:r0','relationship','declared','accepted','human_confirmed',now(),'fixture','r0',$2) RETURNING id",
                str(profile_id), run_id,
            )
            await connection.execute("INSERT INTO assertion_evidence(assertion_id,evidence_locator_id) VALUES($1,$2)", assertion_id, locator_id)
            await connection.execute(
                "INSERT INTO source_connector_definitions(connector_key,definition_version,display_name,provider,connector_type,modes,data_classes,permissions) "
                "VALUES('r0_fixture','1','R0 fixture','fixture','fixture','[\"manual\"]','[]','[]')"
            )
            await connection.execute(
                "INSERT INTO connector_instances(connector_key,definition_version,profile_id,display_name) VALUES('r0_fixture','1',$1,'R0 fixture instance')",
                profile_id,
            )
        finally:
            await connection.close()
        await _apply_twice(url)
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM requests WHERE id=$1", request_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM request_chat_messages WHERE request_id=$1", request_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM connector_instances WHERE profile_id=$1", profile_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM source_connector_definitions WHERE connector_key='r0_fixture' AND definition_version='1'") == 1
            assert await connection.fetchval("SELECT count(*) FROM assertions WHERE id=$1 AND status='accepted' AND object_ref='GraphNode:r0'", assertion_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM assertion_evidence WHERE assertion_id=$1", assertion_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM export_snapshots WHERE id=$1", snapshot_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM source_artifacts WHERE id=$1", artifact_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM evidence_locators WHERE id=$1", locator_id) == 1
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_dashboard_completed_request_query_is_schema_compatible_baseline():
    admin, name, url = await _temporary_database("dashboard_query")
    try:
        await _apply_twice(url)
        connection = await asyncpg.connect(url)
        try:
            row = await connection.fetchrow(
                "SELECT updated_at,response_received_at,completed_at,deadline_at,deadline_basis "
                "FROM requests LIMIT 1"
            )
            assert row is None
        finally:
            await connection.close()
    finally:
        await _drop_database(admin, name)
