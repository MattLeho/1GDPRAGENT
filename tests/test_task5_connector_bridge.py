from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlparse
from urllib.request import url2pathname
from uuid import uuid4

import asyncpg
import pytest

import connectors.bridge as bridge_module
from connectors.bridge import (
    ConnectorIngestionBridge,
    ConnectorIngestionResult,
    ConnectorPermissionDenied,
    connector_record_signature,
)
from connectors.models import ConnectorRawRecord
from db.postgres import PostgresClient
from ingestion.storage import StorageRoots
from test_task1_database_integration import migrated_database


NOW = datetime(2025, 6, 7, 8, 9, tzinfo=timezone.utc)


def _record(
    *, connector_instance_id=None, payload=b"opaque source record",
    media_type="application/octet-stream", required_permissions=("records.read",),
    source_metadata=None, source_record_id="provider-record-1",
) -> ConnectorRawRecord:
    connector_instance_id = connector_instance_id or uuid4()
    metadata = source_metadata or {"provider_kind": "fixture", "remote_sequence": 7}
    signature = connector_record_signature(
        source_record_id=source_record_id, source_record_version="3", payload=payload,
        data_class="fixture.records", occurred_at=NOW, media_type=media_type,
        source_metadata=metadata,
    )
    return ConnectorRawRecord(
        connector_instance_id=connector_instance_id,
        source_record_id=source_record_id, source_record_version="3",
        record_signature=signature, data_class="fixture.records", occurred_at=NOW,
        observed_at=NOW, media_type=media_type, payload=payload,
        source_metadata=metadata, required_permissions=required_permissions,
    )


def _context(instance_id, *, enabled=("records.read",)):
    return {
        "analysis_run_id": uuid4(), "connector_instance_id": instance_id,
        "profile_id": None, "account_key": "primary", "enabled_permissions": list(enabled),
        "connector_key": "fixture.connector", "definition_version": "1",
        "provider": "Fixture Provider", "connector_type": "synthetic",
        "data_classes": ["fixture.records"],
        "permissions": [{
            "key": "records.read", "access": "read", "data_class": "fixture.records",
            "description": "Read fixture records", "required": True,
            "enabled_by_default": False,
        }],
    }


def test_connector_record_signature_is_canonical_and_observation_independent():
    common = dict(
        source_record_id="remote/42", source_record_version="v2", payload=b'{"a":1}',
        data_class="browser.history", occurred_at=NOW, media_type="application/json",
    )
    first = connector_record_signature(**common, source_metadata={"z": 2, "a": {"y": 1, "x": 0}})
    reordered = connector_record_signature(**common, source_metadata={"a": {"x": 0, "y": 1}, "z": 2})
    changed = connector_record_signature(**{**common, "payload": b'{"a":2}'}, source_metadata={"z": 2, "a": {"y": 1, "x": 0}})
    assert first == reordered
    assert first != changed
    assert len(first) == 64 and first == first.casefold()


@pytest.mark.asyncio
async def test_permission_denial_happens_before_snapshot_raw_record_or_blob_write(tmp_path, monkeypatch):
    record = _record()
    bridge = object.__new__(ConnectorIngestionBridge)
    bridge._load_context = AsyncMock(return_value=_context(record.connector_instance_id, enabled=()))
    bridge._snapshot_for = AsyncMock(side_effect=AssertionError("snapshot must not be created"))
    bridge._claim_raw_record = AsyncMock(side_effect=AssertionError("raw record must not be written"))
    monkeypatch.setattr(bridge_module, "write_raw_blob", lambda *_: pytest.fail("blob must not be written"))

    with pytest.raises(ConnectorPermissionDenied, match="disabled"):
        await bridge.ingest(record, sync_run_id=uuid4())
    bridge._snapshot_for.assert_not_awaited()
    bridge._claim_raw_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_like_record_routes_through_task3_and_persists_provenance_status(tmp_path):
    record = _record(
        payload=b'{"event":"visited","url":"https://example.test"}',
        media_type="application/json", source_metadata={"file_name": "history.json"},
    )
    artifact_id, raw_id, locator_id, snapshot_id = uuid4(), uuid4(), uuid4(), uuid4()
    bridge = object.__new__(ConnectorIngestionBridge)
    bridge.roots = StorageRoots.from_base(tmp_path / "data").ensure()
    bridge.postgres = SimpleNamespace(execute=AsyncMock(return_value=[]))
    bridge.bulk = SimpleNamespace(process_file=AsyncMock(return_value=SimpleNamespace(
        artifact_id=artifact_id, event_count=2, ingestion_status="completed",
    )))
    bridge._load_context = AsyncMock(return_value=_context(record.connector_instance_id))
    bridge._snapshot_for = AsyncMock(return_value=snapshot_id)
    bridge._validate_snapshot = AsyncMock()
    bridge._claim_raw_record = AsyncMock(return_value={
        "id": raw_id, "source_artifact_id": None, "ingestion_status": "ingesting",
    })
    bridge._ensure_root_locator = AsyncMock(return_value=locator_id)

    result = await bridge.ingest(record, sync_run_id=uuid4())

    assert result.source_artifact_id == artifact_id
    assert result.root_locator_id == locator_id
    assert result.event_count == 2 and not result.duplicate
    bridge.bulk.process_file.assert_awaited_once()
    sql = "\n".join(call.args[0] for call in bridge.postgres.execute.await_args_list)
    assert "source_artifact_id=$2,ingestion_status='ingested'" in sql
    assert not any(term in sql.casefold() for term in ("neo4j", "interested_in", "importance", "retention"))


@pytest.mark.asyncio
async def test_ingested_duplicate_short_circuits_without_new_snapshot_or_payload_write(monkeypatch):
    record = _record()
    expected = ConnectorIngestionResult(
        raw_record_id=uuid4(), source_artifact_id=uuid4(), analysis_run_id=uuid4(),
        export_snapshot_id=uuid4(), root_locator_id=uuid4(), ingestion_status="ingested",
        duplicate=True,
    )
    bridge = object.__new__(ConnectorIngestionBridge)
    bridge._load_context = AsyncMock(return_value=_context(record.connector_instance_id))
    bridge._claim_raw_record = AsyncMock(return_value={
        "id": expected.raw_record_id, "source_artifact_id": expected.source_artifact_id,
        "ingestion_status": "ingested",
    })
    bridge._duplicate_result = AsyncMock(return_value=expected)
    bridge._snapshot_for = AsyncMock(side_effect=AssertionError("duplicate must reuse original snapshot"))
    monkeypatch.setattr(bridge_module, "write_raw_blob", lambda *_: pytest.fail("duplicate must not rewrite payload"))

    assert await bridge.ingest(record, sync_run_id=uuid4()) == expected
    bridge._snapshot_for.assert_not_awaited()
    bridge._duplicate_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_bridge_database_idempotency_permission_boundary_and_exact_provenance(tmp_path, migrated_database):
    url, _, _ = migrated_database
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,status,pipeline_version) VALUES('connector-sync','running','task5-v1') RETURNING id"
        )
        await connection.execute(
            """INSERT INTO source_connector_definitions
            (connector_key,definition_version,display_name,provider,connector_type,modes,data_classes,permissions)
            VALUES('fixture.connector','1','Fixture','Fixture Provider','synthetic','["snapshot_import"]',
            '["fixture.records"]','[{"key":"records.read","access":"read","data_class":"fixture.records",
            "description":"Read fixture records","required":true,"enabled_by_default":false}]')"""
        )
        instance_id = await connection.fetchval(
            """INSERT INTO connector_instances
            (connector_key,definition_version,account_key,display_name,status,enabled_permissions)
            VALUES('fixture.connector','1','primary','Fixture primary','connected','["records.read"]') RETURNING id"""
        )
        sync_run_id = await connection.fetchval(
            """INSERT INTO connector_sync_runs
            (connector_instance_id,analysis_run_id,run_kind,status)
            VALUES($1,$2,'sync','running') RETURNING id""", instance_id, run_id,
        )
    finally:
        await connection.close()

    client = PostgresClient(url)
    bridge = ConnectorIngestionBridge(client, roots=StorageRoots.from_base(tmp_path / "connector-data"))
    record = _record(connector_instance_id=instance_id)
    try:
        first = await bridge.ingest(record, sync_run_id=sync_run_id)
        second = await bridge.ingest(record, sync_run_id=sync_run_id)
        assert not first.duplicate and second.duplicate
        assert second.raw_record_id == first.raw_record_id
        assert second.source_artifact_id == first.source_artifact_id
        assert second.root_locator_id == first.root_locator_id

        rows = await client.execute(
            """SELECT crr.ingestion_status,crr.source_artifact_id,sa.source_organisation,
            sa.source_product,sa.source_service,cb.sha256,cb.storage_uri,el.locator_type,
            el.locator,el.raw_hash,el.verified
            FROM connector_raw_records crr
            JOIN source_artifacts sa ON sa.id=crr.source_artifact_id
            JOIN content_blobs cb ON cb.id=sa.content_blob_id
            JOIN evidence_locators el ON el.id=$2
            WHERE crr.id=$1""", first.raw_record_id, first.root_locator_id,
        )
        row = rows[0]
        assert row["ingestion_status"] == "ingested"
        assert row["source_organisation"] == "Fixture Provider"
        assert row["source_product"] == "fixture.connector"
        assert row["source_service"] == "synthetic"
        assert row["sha256"] == hashlib.sha256(record.payload).hexdigest()
        assert row["verified"] and row["raw_hash"] == hashlib.sha256(record.payload).hexdigest()
        assert row["locator_type"] == "text_span"
        locator = json.loads(row["locator"]) if isinstance(row["locator"], str) else dict(row["locator"])
        assert locator == {"byte_start": 0, "byte_end": len(record.payload)}
        assert Path(url2pathname(urlparse(row["storage_uri"]).path)).exists()

        denied = _record(
            connector_instance_id=instance_id, payload=b"must never persist",
            source_record_id="denied", required_permissions=("records.read", "undeclared.read"),
        )
        with pytest.raises(ConnectorPermissionDenied, match="unknown"):
            await bridge.ingest(denied, sync_run_id=sync_run_id)
        assert not await client.execute(
            "SELECT id FROM connector_raw_records WHERE record_signature=$1", denied.record_signature,
        )
        assert not await client.execute(
            "SELECT id FROM content_blobs WHERE sha256=$1", hashlib.sha256(denied.payload).hexdigest(),
        )
    finally:
        await client.close()
