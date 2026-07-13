from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

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
from connectors.runtime import ConnectorRuntime
from connectors.synthetic import SyntheticConnector, SyntheticRecord


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
