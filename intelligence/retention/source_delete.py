"""Capability-gated and audited source deletion execution."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client
from connectors.imap_delete import IMAPTrashDeletion
from connectors.models import ConnectorInstance

from .models import SourceDeletionExecution


class SourceDeletionDenied(RuntimeError):
    pass


class SourceDeletionService:
    def __init__(self, postgres: PostgresClient | None = None, *, adapters: dict[str, Any] | None = None) -> None:
        self.postgres = postgres or get_postgres_client()
        self.adapters = adapters or {"email.imap": IMAPTrashDeletion()}

    async def execute(self, deletion_plan_item_id: UUID) -> SourceDeletionExecution:
        pool = await self.postgres._get_pool()
        execution_id = uuid4()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", str(deletion_plan_item_id))
            row = await connection.fetchrow(
                """SELECT dpi.*,dp.status plan_status,dp.dry_run,rd.classification,rd.review_status,
                   crr.connector_instance_id,crr.source_metadata,ci.connector_key,ci.definition_version,
                   ci.profile_id,ci.account_key,ci.display_name,ci.status connector_status,
                   ci.enabled_permissions,ci.configuration,ci.credential_id,ci.last_sync_at,ci.next_sync_at,
                   ci.created_at connector_created_at,ci.updated_at connector_updated_at,
                   scd.supports_source_delete
                FROM deletion_plan_items dpi
                JOIN deletion_plans dp ON dp.id=dpi.deletion_plan_id
                JOIN retention_decisions rd ON rd.id=dpi.retention_decision_id
                JOIN connector_raw_records crr ON crr.source_artifact_id=dpi.source_artifact_id
                JOIN connector_instances ci ON ci.id=crr.connector_instance_id
                JOIN source_connector_definitions scd ON scd.connector_key=ci.connector_key AND scd.definition_version=ci.definition_version
                WHERE dpi.id=$1 FOR UPDATE OF dpi""", deletion_plan_item_id,
            )
            if not row:
                raise SourceDeletionDenied("plan item has no connector-backed source record")
            existing = await connection.fetchrow(
                "SELECT * FROM source_deletion_executions WHERE deletion_plan_item_id=$1", deletion_plan_item_id,
            )
            if existing:
                raise SourceDeletionDenied(f"source deletion already has audit status {existing['provider_status']}")
            self._preflight(row)
            await connection.execute(
                """INSERT INTO source_deletion_executions(
                   id,deletion_plan_item_id,connector_instance_id,provider_action,reversible,
                   provider_status,audit_payload)
                   VALUES($1,$2,$3,'move_to_trash',TRUE,'initiated',$4::jsonb)""",
                execution_id, deletion_plan_item_id, row["connector_instance_id"],
                json.dumps({"capability_verified": True, "source_identity": {
                    "mailbox": _decoded(row["source_metadata"]).get("mailbox"),
                    "uid": _decoded(row["source_metadata"]).get("uid"),
                    "uidvalidity": _decoded(row["source_metadata"]).get("uidvalidity"),
                }}, sort_keys=True),
            )
            instance = self._instance(row)
            metadata = _decoded(row["source_metadata"])
        adapter = self.adapters.get(instance.definition_key)
        if adapter is None:
            await self._failed(execution_id, "no tested source-delete adapter")
            raise SourceDeletionDenied("no tested source-delete adapter")
        try:
            result = await adapter.execute(instance, metadata)
        except Exception as exc:
            await self._failed(execution_id, str(exc))
            raise
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """UPDATE source_deletion_executions SET provider_action=$2,reversible=$3,
                   provider_response_id=$4,provider_status=$5,
                   audit_payload=audit_payload || $6::jsonb WHERE id=$1 AND provider_status='initiated'
                   RETURNING *""",
                execution_id, result.provider_action, result.reversible,
                result.provider_response_id, result.provider_status,
                json.dumps({"acknowledged": True}),
            )
            if not row:
                raise RuntimeError("source deletion audit changed before provider acknowledgement")
            await connection.execute(
                "UPDATE deletion_plan_items SET stage='executed' WHERE id=$1 AND stage='eligible_for_delete'",
                deletion_plan_item_id,
            )
        return SourceDeletionExecution(
            id=row["id"], deletion_plan_item_id=row["deletion_plan_item_id"],
            connector_instance_id=row["connector_instance_id"], provider_action=row["provider_action"],
            reversible=row["reversible"], provider_response_id=row["provider_response_id"],
            provider_status=row["provider_status"], executed_at=row["executed_at"],
        )

    @staticmethod
    def _preflight(row) -> None:
        if row["dry_run"] or row["plan_status"] != "approved":
            raise SourceDeletionDenied("source deletion requires an approved non-dry-run plan")
        if row["item_group"] != "eligible" or row["stage"] != "eligible_for_delete":
            raise SourceDeletionDenied("source deletion item is not eligible after grace")
        if row["action"] != "source_delete" or not row["source_delete_capability"] or not row["supports_source_delete"]:
            raise SourceDeletionDenied("source connector lacks verified source-delete capability")
        enabled_permissions = set(_decoded(row["enabled_permissions"]) or ())
        if "mail.source_delete" not in enabled_permissions:
            raise SourceDeletionDenied("source deletion requires the enabled mail.source_delete permission")
        if row["review_status"] != "approved" or row["classification"] not in {"LOW_VALUE_BULK", "SPAM"}:
            raise SourceDeletionDenied("retention decision is not approved low-value/spam")

    @staticmethod
    def _instance(row) -> ConnectorInstance:
        return ConnectorInstance(
            id=row["connector_instance_id"], definition_key=row["connector_key"],
            definition_version=row["definition_version"], profile_id=row["profile_id"],
            account_key=row["account_key"], display_name=row["display_name"],
            status=row["connector_status"], enabled_permissions=tuple(_decoded(row["enabled_permissions"])),
            configuration=dict(_decoded(row["configuration"])), credential_id=row["credential_id"],
            last_sync_at=row["last_sync_at"], next_sync_at=row["next_sync_at"],
            created_at=row["connector_created_at"], updated_at=row["connector_updated_at"],
        )

    async def _failed(self, execution_id: UUID, message: str) -> None:
        await self.postgres.execute(
            """UPDATE source_deletion_executions SET provider_status='failed',
               audit_payload=audit_payload || $2::jsonb WHERE id=$1 AND provider_status='initiated'""",
            execution_id, json.dumps({"error": message}),
        )


def _decoded(value):
    return json.loads(value) if isinstance(value, str) else value
