from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest

from connectors.bridge import ConnectorIngestionResult
from connectors.models import (
    ConnectorCursor, ConnectorInstance, ConnectorMode, ConnectorPermission,
    ConnectorStatus, PermissionAccess, SourceConnectorDefinition, SyncRunKind,
    SyncRunStatus,
)
from connectors.registry import (
    ConnectorPermissionError, ConnectorRegistry, ConnectorRegistryError,
    ConnectorSyncBatch, validate_enabled_permissions,
)
from connectors.runtime import ConnectorRunRejected, ConnectorRuntime
from connectors.bridge import ConnectorIngestionBridge
from connectors.repository import ConnectorRepository
from connectors.synthetic import SyntheticConnector, SyntheticRecord
from db.postgres import PostgresClient
from ingestion.storage import StorageRoots
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _definition(*, schema=None) -> SourceConnectorDefinition:
    return SourceConnectorDefinition(
        key="synthetic.fixture", version="1", display_name="Synthetic fixture",
        provider="local", connector_type="synthetic",
        modes=(ConnectorMode.SNAPSHOT_IMPORT, ConnectorMode.INCREMENTAL_POLL),
        data_classes=("synthetic_event",),
        permissions=(ConnectorPermission(
            key="records.read", access=PermissionAccess.READ,
            data_class="synthetic_event", description="Read fixture records", required=True,
        ),),
        supports_backfill=True, supports_incremental=True,
        configuration_schema=schema or {"type": "object", "properties": {}},
    )


def _instance(definition: SourceConnectorDefinition) -> ConnectorInstance:
    return ConnectorInstance(
        id=uuid4(), definition_key=definition.key,
        definition_version=definition.version, display_name="Fixture",
        status=ConnectorStatus.CONNECTED, enabled_permissions=("records.read",),
        created_at=NOW, updated_at=NOW,
    )


def test_registry_rejects_secret_configuration_and_permission_overreach():
    registry = ConnectorRegistry()
    unsafe = _definition(schema={
        "type": "object", "properties": {"access_token": {"type": "string"}},
    })
    with pytest.raises(ConnectorRegistryError, match="encrypted credential storage"):
        registry.register(unsafe, lambda _: None)

    definition = _definition()
    with pytest.raises(ConnectorPermissionError, match="undeclared"):
        validate_enabled_permissions(definition, ("records.read", "mail.delete"))


@pytest.mark.asyncio
async def test_runtime_ingests_before_advancing_cursor_and_records_canonical_metrics():
    definition = _definition()
    instance = _instance(definition)
    source = SyntheticConnector(instance.id, (
        SyntheticRecord("one", {"value": 1}, required_permissions=("records.read",)),
        SyntheticRecord("two", {"value": 2}, required_permissions=("records.read",)),
    ), observed_at=NOW)

    class Adapter:
        def __init__(self, connector_definition):
            self.definition = connector_definition

        def acquire(self, request):
            page = source.read(request.cursor, limit=10)
            return ConnectorSyncBatch(
                records=page.records, cursor_position=page.cursor_after.position,
                source_watermark=page.cursor_after.source_watermark,
            )

    registry = ConnectorRegistry()
    registry.register(definition, lambda _: Adapter(definition))
    cursor = source.initial_cursor(updated_at=NOW)
    run = SimpleNamespace(id=uuid4())
    completed = SimpleNamespace(status=SyncRunStatus.COMPLETED)
    repository = SimpleNamespace(
        get_instance=AsyncMock(return_value=instance),
        get_cursor=AsyncMock(return_value=cursor),
        start_sync_run=AsyncMock(return_value=run),
        upsert_cursor=AsyncMock(return_value=cursor.model_copy(update={"position": {"offset": 2}})),
        finish_sync_run=AsyncMock(return_value=completed),
    )
    bridge = SimpleNamespace(ingest=AsyncMock(side_effect=(
        ConnectorIngestionResult(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), "completed", False, 3),
        ConnectorIngestionResult(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), "ingested", True, 0),
    )))

    result = await ConnectorRuntime(registry, repository, bridge).run(
        instance.id, uuid4(), kind=SyncRunKind.SYNC,
    )

    assert result is completed
    assert bridge.ingest.await_count == 2
    repository.upsert_cursor.assert_awaited_once()
    finish = repository.finish_sync_run.await_args.kwargs
    assert finish["status"] is SyncRunStatus.COMPLETED
    assert finish["artefacts_discovered"] == 2
    assert finish["events_produced"] == 3
    assert finish["duplicates_skipped"] == 1
    assert finish["cursor_after"] == {"offset": 2}


@pytest.mark.asyncio
async def test_runtime_does_not_advance_cursor_when_canonical_ingestion_fails():
    definition = _definition()
    instance = _instance(definition)
    source = SyntheticConnector(instance.id, (SyntheticRecord("one", {"value": 1}),), observed_at=NOW)

    class Adapter:
        def __init__(self, connector_definition):
            self.definition = connector_definition

        def acquire(self, request):
            page = source.read(request.cursor)
            return ConnectorSyncBatch(records=page.records, cursor_position=page.cursor_after.position)

    registry = ConnectorRegistry()
    registry.register(definition, lambda _: Adapter(definition))
    cursor = source.initial_cursor(updated_at=NOW)
    repository = SimpleNamespace(
        get_instance=AsyncMock(return_value=instance), get_cursor=AsyncMock(return_value=cursor),
        start_sync_run=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
        upsert_cursor=AsyncMock(), finish_sync_run=AsyncMock(return_value=SimpleNamespace()),
    )
    bridge = SimpleNamespace(ingest=AsyncMock(side_effect=RuntimeError("ingestion failed")))

    with pytest.raises(RuntimeError, match="ingestion failed"):
        await ConnectorRuntime(registry, repository, bridge).run(instance.id, uuid4())

    repository.upsert_cursor.assert_not_awaited()
    failed = repository.finish_sync_run.await_args.kwargs
    assert failed["status"] is SyncRunStatus.FAILED
    assert failed["cursor_after"] == {"offset": 0}
    assert failed["errors"] == 1


@pytest.mark.asyncio
async def test_synthetic_connector_full_wave1_gate(tmp_path, migrated_database):
    """Backfill/lifecycle/dedup all cross the real PostgreSQL evidence bridge."""

    url, _, _ = migrated_database
    client = PostgresClient(url)
    repository = ConnectorRepository(client)
    definition = _definition()
    registry = ConnectorRegistry()
    source_by_instance = {}

    class Adapter:
        def __init__(self, connector_definition, source):
            self.definition = connector_definition
            self.source = source

        def acquire(self, request):
            page = self.source.read(request.cursor, limit=100)
            return ConnectorSyncBatch(
                records=page.records, cursor_position=page.cursor_after.position,
                source_watermark=page.cursor_after.source_watermark,
            )

    registry.register(
        definition,
        lambda instance: Adapter(definition, source_by_instance[instance.id]),
    )
    await repository.declare_definition(definition)
    instance = await repository.create_instance(
        definition, display_name="Wave 1 fixture", enabled_permissions=("records.read",),
        status=ConnectorStatus.CONNECTED,
    )
    source_by_instance[instance.id] = SyntheticConnector(instance.id, (
        SyntheticRecord(
            "provider/1", {"kind": "fixture", "value": 1},
            media_type="application/octet-stream", required_permissions=("records.read",),
        ),
        SyntheticRecord(
            "provider/2", {"kind": "fixture", "value": 2},
            media_type="application/octet-stream", required_permissions=("records.read",),
        ),
    ), observed_at=NOW)

    connection = await asyncpg.connect(url)
    try:
        analysis_run_id = await connection.fetchval(
            """INSERT INTO analysis_runs(run_type,status,pipeline_version)
               VALUES('connector-sync','running','task5-wave1') RETURNING id"""
        )
    finally:
        await connection.close()

    runtime = ConnectorRuntime(
        registry, repository,
        ConnectorIngestionBridge(client, roots=StorageRoots.from_base(tmp_path / "wave1-data")),
    )
    first = await runtime.run(instance.id, analysis_run_id)
    assert first.status is SyncRunStatus.COMPLETED
    assert first.artefacts_discovered == 2 and first.duplicates_skipped == 0
    assert first.cursor_after == {"offset": 2}

    # A separate backfill cursor intentionally re-observes the same records;
    # canonical signatures reuse the original raw records and evidence.
    backfill = await runtime.run(
        instance.id, analysis_run_id, kind=SyncRunKind.BACKFILL, cursor_key="backfill",
    )
    assert backfill.status is SyncRunStatus.COMPLETED
    assert backfill.duplicates_skipped == 2
    assert backfill.cursor_after == {"offset": 2}

    await repository.set_status(instance.id, ConnectorStatus.PAUSED)
    with pytest.raises(ConnectorRunRejected, match="paused"):
        await runtime.run(instance.id, analysis_run_id)
    await repository.set_status(instance.id, ConnectorStatus.CONNECTED)
    resumed = await runtime.run(instance.id, analysis_run_id)
    assert resumed.cursor_before == {"offset": 2}
    assert resumed.artefacts_discovered == 0

    await repository.set_status(instance.id, ConnectorStatus.DISCONNECTED)
    with pytest.raises(ConnectorRunRejected, match="disconnected"):
        await runtime.run(instance.id, analysis_run_id)
    await repository.set_status(instance.id, ConnectorStatus.CONNECTED)
    assert (await repository.get_cursor(instance.id)).position == {"offset": 2}

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM connector_raw_records WHERE connector_instance_id=$1) AS raw_count,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                WHERE es.metadata->>'connector_instance_id'=$2) AS artifact_count,
              (SELECT COUNT(*) FROM evidence_locators el JOIN source_artifacts sa ON sa.id=el.artifact_id
                JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                WHERE es.metadata->>'connector_instance_id'=$2 AND el.verified) AS locator_count""",
            instance.id, str(instance.id),
        )
        assert dict(counts) == {"raw_count": 2, "artifact_count": 2, "locator_count": 2}
    finally:
        await connection.close()
        await client.close()
