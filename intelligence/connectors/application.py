"""Composition root for built-in SourceConnectors and Task 2 execution entrypoints."""
from __future__ import annotations

import json
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client

from .bridge import ConnectorIngestionBridge
from .credentials import CredentialUnavailable
from .definitions import (
    AI_CONVERSATION_DEFINITION, BROWSER_HISTORY_DEFINITION, FILESYSTEM_DEFINITION,
    IMAP_EMAIL_DEFINITION, PHOTO_FOLDER_DEFINITION,
)
from .ai_conversations import AIConversationSnapshotConnector
from .filesystem import FolderConnector
from .imap import IMAPSourceConnector
from .models import ConnectorStatus, ConnectorSyncRun, SourceConnectorDefinition, SyncRunKind
from .registry import ConnectorRegistry, ConnectorSyncBatch
from .repository import ConnectorRepository
from .runtime import ConnectorRuntime


class _PushOnlyConnector:
    def __init__(self, instance) -> None:
        self.instance = instance
        self.definition = BROWSER_HISTORY_DEFINITION

    def acquire(self, request):
        raise RuntimeError("browser history is delivered through the authenticated local bridge")


def built_in_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(BROWSER_HISTORY_DEFINITION, _PushOnlyConnector)
    registry.register(IMAP_EMAIL_DEFINITION, IMAPSourceConnector)
    registry.register(AI_CONVERSATION_DEFINITION, AIConversationSnapshotConnector)
    registry.register(FILESYSTEM_DEFINITION, FolderConnector)
    registry.register(PHOTO_FOLDER_DEFINITION, FolderConnector)
    return registry


class ConnectorApplication:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()
        self.registry = built_in_registry()
        self.repository = ConnectorRepository(self.postgres)
        self.runtime = ConnectorRuntime(
            self.registry, self.repository, ConnectorIngestionBridge(self.postgres),
        )

    async def declare_definitions(self) -> tuple[SourceConnectorDefinition, ...]:
        await self.runtime.declare_definitions()
        return self.registry.definitions()

    async def run_instance(
        self, instance_id: UUID, *, kind: SyncRunKind = SyncRunKind.SYNC,
        cursor_key: str = "default",
    ) -> ConnectorSyncRun:
        instance = await self.repository.get_instance(instance_id)
        rows = await self.postgres.execute(
            """INSERT INTO analysis_runs(run_type,profile_id,status,pipeline_version,configuration,started_at)
               VALUES('connector_sync',$1,'running','task5-connector-v1',$2::jsonb,NOW()) RETURNING id""",
            instance.profile_id,
            json.dumps({"connector_instance_id": str(instance_id), "kind": kind.value}, sort_keys=True),
        )
        analysis_run_id = rows[0]["id"]
        try:
            result = await self.runtime.run(
                instance_id, analysis_run_id, kind=kind, cursor_key=cursor_key,
            )
            await self.postgres.execute(
                "UPDATE analysis_runs SET status='completed',completed_at=NOW() WHERE id=$1",
                analysis_run_id,
            )
            await self.postgres.execute(
                """UPDATE connector_instances SET status='connected',last_sync_at=NOW(),
                   next_sync_at=NOW()+INTERVAL '15 minutes',last_error=NULL,updated_at=NOW()
                   WHERE id=$1 AND status IN ('connected','degraded')""", instance_id,
            )
            return result
        except Exception as exc:
            await self.postgres.execute(
                "UPDATE analysis_runs SET status='failed',completed_at=NOW(),error=$2 WHERE id=$1",
                analysis_run_id, str(exc),
            )
            if isinstance(exc, CredentialUnavailable):
                try:
                    from .models import ConnectorStatus
                    await self.repository.set_status(
                        instance_id, ConnectorStatus.AUTHENTICATION_REQUIRED,
                    )
                except Exception:
                    pass
            else:
                await self.postgres.execute(
                    """UPDATE connector_instances SET status='degraded',
                       next_sync_at=NOW()+INTERVAL '5 minutes',
                       last_error=$2::jsonb,updated_at=NOW()
                       WHERE id=$1 AND status IN ('connected','degraded')""",
                    instance_id, json.dumps({"type": type(exc).__name__, "message": str(exc)}),
                )
            raise
