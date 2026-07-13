"""Provider-neutral connector sync runtime.

A run is complete only after every acquired payload has crossed the canonical
Task 3 ingestion bridge.  This prevents cursor advancement from outrunning
durable provenance and prevents adapters from becoming a parallel event path.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .bridge import ConnectorIngestionResult
from .models import ConnectorStatus, ConnectorSyncRun, SyncRunKind, SyncRunStatus
from .registry import ConnectorRegistry, validate_record_permissions
from .repository import ConnectorRepository


class ConnectorRunRejected(RuntimeError):
    pass


class CanonicalIngestionBridge(Protocol):
    async def ingest(
        self, record, *, sync_run_id: UUID,
        export_snapshot_id: UUID | None = None,
    ) -> ConnectorIngestionResult: ...


class ConnectorRuntime:
    def __init__(
        self, registry: ConnectorRegistry, repository: ConnectorRepository,
        bridge: CanonicalIngestionBridge,
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.bridge = bridge

    async def declare_definitions(self) -> None:
        for definition in self.registry.definitions():
            await self.repository.declare_definition(definition)

    async def run(
        self,
        instance_id: UUID,
        analysis_run_id: UUID,
        *,
        kind: SyncRunKind = SyncRunKind.SYNC,
        cursor_key: str = "default",
    ) -> ConnectorSyncRun:
        instance = await self.repository.get_instance(instance_id)
        if instance.status not in {ConnectorStatus.CONNECTED, ConnectorStatus.DEGRADED}:
            raise ConnectorRunRejected(
                f"connector instance in {instance.status.value!r} state cannot run"
            )
        definition = self.registry.get_definition(
            instance.definition_key, instance.definition_version
        )
        cursor = await self.repository.get_cursor(instance.id, cursor_key)
        cursor_before = dict(cursor.position) if cursor else {}
        run = await self.repository.start_sync_run(
            instance.id, analysis_run_id, kind, cursor_before
        )
        discovered = duplicates = events = errors = 0
        cursor_after = cursor_before
        try:
            batch = await self.registry.dispatch(instance, kind, cursor)
            errors = batch.errors
            for record in batch.records:
                discovered += 1
                if record.connector_instance_id != instance.id:
                    raise ValueError("connector returned a record for another instance")
                validate_record_permissions(definition, instance.enabled_permissions, record)
                ingested = await self.bridge.ingest(record, sync_run_id=run.id)
                events += ingested.event_count
                if ingested.duplicate:
                    duplicates += 1
            if batch.cursor_position is not None:
                saved = await self.repository.upsert_cursor(
                    instance.id, batch.cursor_position, cursor_key=cursor_key,
                    version=cursor.version if cursor else 1,
                    source_watermark=batch.source_watermark,
                )
                cursor_after = dict(saved.position)
            return await self.repository.finish_sync_run(
                run.id, status=SyncRunStatus.COMPLETED, cursor_after=cursor_after,
                artefacts_discovered=discovered, events_produced=events,
                duplicates_skipped=duplicates, errors=errors,
            )
        except Exception as exc:
            errors += 1
            await self.repository.finish_sync_run(
                run.id, status=SyncRunStatus.FAILED, cursor_after=cursor_before,
                artefacts_discovered=discovered, events_produced=events,
                duplicates_skipped=duplicates, errors=errors,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise
