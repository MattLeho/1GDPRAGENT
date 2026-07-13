"""PostgreSQL persistence for connector acquisition lifecycle state."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client

from .models import (
    ConnectorCursor,
    ConnectorInstance,
    ConnectorRawRecord,
    ConnectorStatus,
    ConnectorSyncRun,
    SourceConnectorDefinition,
    SyncRunKind,
    SyncRunStatus,
)
from .registry import validate_definition, validate_enabled_permissions
from .lifecycle import transition


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class ConnectorRepository:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def declare_definition(self, definition: SourceConnectorDefinition) -> None:
        validate_definition(definition)
        await self.postgres.execute(
            """INSERT INTO source_connector_definitions(
                 connector_key,definition_version,display_name,provider,connector_type,modes,
                 data_classes,permissions,supports_backfill,supports_incremental,
                 supports_source_delete,supports_remote_delete_request,configuration_schema)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9,$10,$11,$12,$13::jsonb)
               ON CONFLICT(connector_key,definition_version) DO UPDATE SET
                 display_name=EXCLUDED.display_name,provider=EXCLUDED.provider,
                 connector_type=EXCLUDED.connector_type,modes=EXCLUDED.modes,
                 data_classes=EXCLUDED.data_classes,permissions=EXCLUDED.permissions,
                 supports_backfill=EXCLUDED.supports_backfill,
                 supports_incremental=EXCLUDED.supports_incremental,
                 supports_source_delete=EXCLUDED.supports_source_delete,
                 supports_remote_delete_request=EXCLUDED.supports_remote_delete_request,
                 configuration_schema=EXCLUDED.configuration_schema""",
            definition.key, definition.version, definition.display_name, definition.provider,
            definition.connector_type, _json([mode.value for mode in definition.modes]),
            _json(list(definition.data_classes)),
            _json([permission.model_dump(mode="json") for permission in definition.permissions]),
            definition.supports_backfill, definition.supports_incremental,
            definition.supports_source_delete, definition.supports_remote_delete_request,
            _json(definition.configuration_schema),
        )

    async def create_instance(
        self,
        definition: SourceConnectorDefinition,
        *,
        display_name: str,
        enabled_permissions: Iterable[str],
        profile_id: UUID | None = None,
        account_key: str = "default",
        configuration: dict[str, Any] | None = None,
        credential_id: UUID | None = None,
        status: ConnectorStatus = ConnectorStatus.DISCONNECTED,
    ) -> ConnectorInstance:
        enabled = validate_enabled_permissions(definition, enabled_permissions)
        # Let the frozen model reject credential-shaped public configuration.
        now = datetime.now().astimezone()
        candidate = ConnectorInstance(
            id=uuid4(), definition_key=definition.key, definition_version=definition.version,
            profile_id=profile_id, account_key=account_key, display_name=display_name,
            status=status, enabled_permissions=enabled, configuration=configuration or {},
            credential_id=credential_id, created_at=now, updated_at=now,
        )
        rows = await self.postgres.execute(
            """INSERT INTO connector_instances(
                 id,connector_key,definition_version,profile_id,account_key,display_name,status,
                 enabled_permissions,configuration,credential_id)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10)
               RETURNING *""",
            candidate.id, definition.key, definition.version, profile_id, account_key,
            display_name, status.value, _json(list(enabled)), _json(candidate.configuration), credential_id,
        )
        return self._instance(rows[0])

    async def get_instance(self, instance_id: UUID) -> ConnectorInstance:
        rows = await self.postgres.execute("SELECT * FROM connector_instances WHERE id=$1", instance_id)
        if not rows:
            raise LookupError(f"connector instance {instance_id} does not exist")
        return self._instance(rows[0])

    async def list_instances(self, *, profile_id: UUID | None = None) -> list[ConnectorInstance]:
        if profile_id is None:
            rows = await self.postgres.execute(
                "SELECT * FROM connector_instances ORDER BY created_at,id"
            )
        else:
            rows = await self.postgres.execute(
                "SELECT * FROM connector_instances WHERE profile_id=$1 ORDER BY created_at,id",
                profile_id,
            )
        return [self._instance(row) for row in rows]

    async def set_status(
        self, instance_id: UUID, status: ConnectorStatus,
    ) -> ConnectorInstance:
        current = await self.get_instance(instance_id)
        candidate = transition(current, status)
        rows = await self.postgres.execute(
            """UPDATE connector_instances SET status=$2,next_sync_at=$3,updated_at=$4
               WHERE id=$1 AND status=$5 RETURNING *""",
            instance_id, candidate.status.value, candidate.next_sync_at,
            candidate.updated_at, current.status.value,
        )
        if not rows:
            raise RuntimeError("connector status changed concurrently")
        return self._instance(rows[0])

    async def set_enabled_permissions(
        self, instance_id: UUID, definition: SourceConnectorDefinition,
        enabled_permissions: Iterable[str], *, actor: str,
    ) -> ConnectorInstance:
        if not actor.strip():
            raise ValueError("permission changes require an audit actor")
        current = await self.get_instance(instance_id)
        if (current.definition_key, current.definition_version) != (definition.key, definition.version):
            raise ValueError("connector instance does not match definition")
        enabled = validate_enabled_permissions(definition, enabled_permissions)
        rows = await self.postgres.execute(
            """WITH changed AS (
                 UPDATE connector_instances SET enabled_permissions=$2::jsonb,updated_at=NOW()
                 WHERE id=$1 AND enabled_permissions=$3::jsonb RETURNING *
               ), audited AS (
                 INSERT INTO connector_permission_audits(
                   connector_instance_id,actor,permissions_before,permissions_after)
                 SELECT $1,$4,$3::jsonb,$2::jsonb FROM changed
               ) SELECT * FROM changed""",
            instance_id, _json(list(enabled)), _json(list(current.enabled_permissions)), actor.strip(),
        )
        if not rows:
            refreshed = await self.get_instance(instance_id)
            if refreshed.enabled_permissions == enabled:
                return refreshed
            raise RuntimeError("connector permissions changed concurrently")
        return self._instance(rows[0])

    async def get_cursor(self, instance_id: UUID, cursor_key: str = "default") -> ConnectorCursor | None:
        rows = await self.postgres.execute(
            "SELECT * FROM connector_cursors WHERE connector_instance_id=$1 AND cursor_key=$2",
            instance_id, cursor_key,
        )
        return self._cursor(rows[0]) if rows else None

    async def upsert_cursor(
        self,
        instance_id: UUID,
        position: dict[str, Any],
        *,
        cursor_key: str = "default",
        version: int = 1,
        source_watermark: str | None = None,
    ) -> ConnectorCursor:
        if version < 1:
            raise ValueError("cursor version must be positive")
        rows = await self.postgres.execute(
            """INSERT INTO connector_cursors(
                 connector_instance_id,cursor_key,cursor_version,position,source_watermark,updated_at)
               VALUES($1,$2,$3,$4::jsonb,$5,NOW())
               ON CONFLICT(connector_instance_id,cursor_key) DO UPDATE SET
                 cursor_version=EXCLUDED.cursor_version,position=EXCLUDED.position,
                 source_watermark=EXCLUDED.source_watermark,updated_at=NOW()
               RETURNING *""",
            instance_id, cursor_key, version, _json(position), source_watermark,
        )
        return self._cursor(rows[0])

    async def start_sync_run(
        self,
        instance_id: UUID,
        analysis_run_id: UUID,
        kind: SyncRunKind,
        cursor_before: dict[str, Any],
    ) -> ConnectorSyncRun:
        rows = await self.postgres.execute(
            """INSERT INTO connector_sync_runs(
                 connector_instance_id,analysis_run_id,run_kind,status,cursor_before,started_at)
               VALUES($1,$2,$3,'running',$4::jsonb,NOW()) RETURNING *""",
            instance_id, analysis_run_id, kind.value, _json(cursor_before),
        )
        return self._run(rows[0])

    async def finish_sync_run(
        self,
        run_id: UUID,
        *,
        status: SyncRunStatus,
        cursor_after: dict[str, Any],
        artefacts_discovered: int,
        events_produced: int,
        duplicates_skipped: int,
        errors: int,
        error: dict[str, Any] | None = None,
    ) -> ConnectorSyncRun:
        if status not in {SyncRunStatus.COMPLETED, SyncRunStatus.FAILED, SyncRunStatus.CANCELLED}:
            raise ValueError("a finished sync run needs a terminal status")
        metrics = (artefacts_discovered, events_produced, duplicates_skipped, errors)
        if any(value < 0 for value in metrics):
            raise ValueError("sync-run metrics must be non-negative")
        rows = await self.postgres.execute(
            """UPDATE connector_sync_runs SET status=$2,cursor_after=$3::jsonb,
                 artefacts_discovered=$4,events_produced=$5,duplicates_skipped=$6,errors=$7,
                 error=$8::jsonb,completed_at=NOW()
               WHERE id=$1 AND status IN ('pending','running') RETURNING *""",
            run_id, status.value, _json(cursor_after), artefacts_discovered, events_produced,
            duplicates_skipped, errors, _json(error) if error is not None else None,
        )
        if not rows:
            raise LookupError(f"sync run {run_id} does not exist or is already terminal")
        connector_id = rows[0]["connector_instance_id"]
        if status is SyncRunStatus.COMPLETED:
            await self.postgres.execute(
                """UPDATE connector_instances SET last_sync_at=$2,last_error=NULL,
                   status=CASE WHEN status='degraded' THEN 'connected' ELSE status END,
                   updated_at=NOW() WHERE id=$1""",
                connector_id, rows[0]["completed_at"],
            )
        elif status is SyncRunStatus.FAILED:
            await self.postgres.execute(
                """UPDATE connector_instances SET last_error=$2::jsonb,
                   status=CASE WHEN status='connected' THEN 'degraded' ELSE status END,
                   updated_at=NOW() WHERE id=$1""",
                connector_id, _json(error or {"message": "connector sync failed"}),
            )
        return self._run(rows[0])

    async def enqueue_raw_record(self, run_id: UUID, record: ConnectorRawRecord) -> tuple[UUID | None, bool]:
        """Persist queue metadata; payload is handed directly to the canonical bridge."""

        rows = await self.postgres.execute(
            """INSERT INTO connector_raw_records(
                 connector_instance_id,sync_run_id,source_record_id,source_record_version,
                 record_signature,data_class,occurred_at,observed_at,media_type,
                 source_metadata,required_permissions,ingestion_status)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,'queued')
               ON CONFLICT(connector_instance_id,record_signature) DO NOTHING RETURNING id""",
            record.connector_instance_id, run_id, record.source_record_id,
            record.source_record_version, record.record_signature, record.data_class,
            record.occurred_at, record.observed_at, record.media_type,
            _json(record.source_metadata), _json(list(record.required_permissions)),
        )
        return (rows[0]["id"], True) if rows else (None, False)

    async def list_queued(self, instance_id: UUID, *, limit: int = 100) -> list[Any]:
        if not 1 <= limit <= 10_000:
            raise ValueError("queue limit must be between 1 and 10000")
        return await self.postgres.execute(
            """SELECT * FROM connector_raw_records
               WHERE connector_instance_id=$1 AND ingestion_status='queued'
               ORDER BY observed_at,id LIMIT $2""", instance_id, limit,
        )

    async def mark_ingesting(self, raw_record_id: UUID) -> bool:
        rows = await self.postgres.execute(
            """UPDATE connector_raw_records SET ingestion_status='ingesting',error=NULL
               WHERE id=$1 AND ingestion_status IN ('queued','failed') RETURNING id""", raw_record_id,
        )
        return bool(rows)

    async def mark_ingested(self, raw_record_id: UUID, source_artifact_id: UUID) -> bool:
        rows = await self.postgres.execute(
            """UPDATE connector_raw_records SET ingestion_status='ingested',
                 source_artifact_id=$2,error=NULL WHERE id=$1 AND ingestion_status='ingesting'
               RETURNING id""", raw_record_id, source_artifact_id,
        )
        return bool(rows)

    async def mark_failed(self, raw_record_id: UUID, error: dict[str, Any]) -> bool:
        rows = await self.postgres.execute(
            """UPDATE connector_raw_records SET ingestion_status='failed',error=$2::jsonb
               WHERE id=$1 AND ingestion_status IN ('queued','ingesting') RETURNING id""",
            raw_record_id, _json(error),
        )
        return bool(rows)

    @staticmethod
    def _instance(row: Any) -> ConnectorInstance:
        return ConnectorInstance(
            id=row["id"], definition_key=row["connector_key"],
            definition_version=row["definition_version"], profile_id=row["profile_id"],
            account_key=row["account_key"], display_name=row["display_name"],
            status=row["status"], enabled_permissions=tuple(_decoded(row["enabled_permissions"])),
            configuration=dict(_decoded(row["configuration"])), credential_id=row["credential_id"],
            last_sync_at=row["last_sync_at"], next_sync_at=row["next_sync_at"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _cursor(row: Any) -> ConnectorCursor:
        return ConnectorCursor(
            connector_instance_id=row["connector_instance_id"], cursor_key=row["cursor_key"],
            version=row["cursor_version"], position=dict(_decoded(row["position"])),
            source_watermark=row["source_watermark"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _run(row: Any) -> ConnectorSyncRun:
        return ConnectorSyncRun(
            id=row["id"], connector_instance_id=row["connector_instance_id"],
            analysis_run_id=row["analysis_run_id"], kind=row["run_kind"], status=row["status"],
            cursor_before=dict(_decoded(row["cursor_before"])), cursor_after=dict(_decoded(row["cursor_after"])),
            artefacts_discovered=row["artefacts_discovered"], events_produced=row["events_produced"],
            duplicates_skipped=row["duplicates_skipped"], errors=row["errors"],
            started_at=row["started_at"], completed_at=row["completed_at"],
        )
