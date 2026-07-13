"""Canonical connector-record bridge into the Task 3 evidence pipeline.

The bridge owns source acquisition provenance only.  It deliberately does not
write assertions, graph state, interests, importance, or retention outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import mimetypes
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client
from evidence.ledger import EvidenceLedger
from evidence.models import EvidenceLocatorCreate, LocatorType
from ingestion.bulk import BulkIngestionService
from ingestion.storage import StorageRoots, write_raw_blob

from .models import ConnectorRawRecord, PermissionAccess
from .signatures import canonical_json as _canonical_json, connector_record_signature


BRIDGE_VERSION = "task5-connector-bridge-v1"


class ConnectorIngestionError(RuntimeError):
    """Base class for acquisition/provenance failures."""


class ConnectorPermissionDenied(ConnectorIngestionError):
    """Raised before payload persistence when acquisition is not authorised."""


class ConnectorRecordIntegrityError(ConnectorIngestionError):
    """Raised when a producer supplies an invalid deterministic signature."""


@dataclass(frozen=True, slots=True)
class ConnectorIngestionResult:
    raw_record_id: UUID
    source_artifact_id: UUID
    analysis_run_id: UUID
    export_snapshot_id: UUID
    root_locator_id: UUID
    ingestion_status: str
    duplicate: bool
    event_count: int = 0


def _json(value: Any) -> str:
    return _canonical_json(value).decode("utf-8")


def _safe_component(value: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return (cleaned[:120] or fallback)


def _extension_for(record: ConnectorRawRecord) -> str:
    supplied = record.source_metadata.get("file_name") or record.source_metadata.get("path")
    if supplied:
        suffixes = Path(str(supplied)).suffixes
        if suffixes:
            return "".join(suffixes)[-32:]
    return mimetypes.guess_extension(record.media_type.split(";", 1)[0].strip()) or ".bin"


def _is_file_like(record: ConnectorRawRecord) -> bool:
    if record.source_metadata.get("file_name") or record.source_metadata.get("path"):
        return True
    media_type = record.media_type.split(";", 1)[0].strip().casefold()
    return (
        media_type.startswith(("text/", "image/", "audio/", "video/", "message/"))
        or media_type in {
            "application/json", "application/xml", "application/pdf", "application/zip",
            "application/mbox", "application/sqlite", "text/calendar", "text/vcard",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
    )


class ConnectorIngestionBridge:
    def __init__(
        self, postgres: PostgresClient | None = None, *, roots: StorageRoots | None = None,
        bulk_service: BulkIngestionService | None = None,
    ) -> None:
        self.postgres = postgres or get_postgres_client()
        self.roots = (roots or StorageRoots.from_env()).ensure()
        self.ledger = EvidenceLedger(self.postgres)
        self.bulk = bulk_service or BulkIngestionService(
            self.postgres, roots=self.roots, import_roots=(self.roots.blobs.resolve(),),
        )

    async def ingest(
        self, record: ConnectorRawRecord, *, sync_run_id: UUID,
        export_snapshot_id: UUID | None = None,
    ) -> ConnectorIngestionResult:
        expected = connector_record_signature(
            source_record_id=record.source_record_id,
            source_record_version=record.source_record_version,
            payload=record.payload, data_class=record.data_class,
            occurred_at=record.occurred_at, media_type=record.media_type,
            source_metadata=record.source_metadata,
        )
        if record.record_signature != expected:
            raise ConnectorRecordIntegrityError("connector record signature does not match its immutable source fields")
        if not record.payload:
            raise ConnectorRecordIntegrityError("empty connector payload cannot ground an exact root EvidenceLocator")

        context = await self._load_context(record, sync_run_id)
        self._enforce_permissions(record, context)
        raw = await self._claim_raw_record(record, sync_run_id)
        if raw["ingestion_status"] == "ingested":
            return await self._duplicate_result(raw, record)

        snapshot_id = export_snapshot_id or await self._snapshot_for(context)
        await self._validate_snapshot(snapshot_id, context["analysis_run_id"])

        try:
            blob = write_raw_blob(self.roots.blobs, record.payload)
            original_path = self._original_path(record, context)
            if _is_file_like(record):
                processed = await self.bulk.process_file(
                    str(blob.path), analysis_run_id=context["analysis_run_id"],
                    export_snapshot_id=snapshot_id, declared_mime=record.media_type,
                    original_path=original_path,
                )
                artifact_id = processed.artifact_id
                event_count = processed.event_count
            else:
                processed = None
                artifact_id = await self._record_typed_artifact(
                    record, context, snapshot_id, blob, original_path,
                )
                event_count = 0
            locator_id = await self._ensure_root_locator(artifact_id, record)
            await self.postgres.execute(
                """UPDATE connector_raw_records SET source_artifact_id=$2,ingestion_status='ingested',error=NULL
                WHERE id=$1""", raw["id"], artifact_id,
            )
            return ConnectorIngestionResult(
                raw_record_id=raw["id"], source_artifact_id=artifact_id,
                analysis_run_id=context["analysis_run_id"], export_snapshot_id=snapshot_id,
                root_locator_id=locator_id, ingestion_status=(processed.ingestion_status if processed else "completed"),
                duplicate=False, event_count=event_count,
            )
        except Exception as exc:
            await self.postgres.execute(
                """UPDATE connector_raw_records SET ingestion_status='failed',
                error=$2::jsonb WHERE id=$1 AND ingestion_status<>'ingested'""",
                raw["id"], _json({"type": type(exc).__name__, "message": str(exc)}),
            )
            raise

    async def _load_context(self, record: ConnectorRawRecord, sync_run_id: UUID) -> dict[str, Any]:
        rows = await self.postgres.execute(
            """SELECT csr.analysis_run_id,csr.connector_instance_id,ci.profile_id,ci.account_key,
            ci.enabled_permissions,ci.connector_key,ci.definition_version,scd.provider,
            scd.connector_type,scd.data_classes,scd.permissions
            FROM connector_sync_runs csr
            JOIN connector_instances ci ON ci.id=csr.connector_instance_id
            JOIN source_connector_definitions scd ON scd.connector_key=ci.connector_key
              AND scd.definition_version=ci.definition_version
            WHERE csr.id=$1 AND csr.connector_instance_id=$2""",
            sync_run_id, record.connector_instance_id,
        )
        if not rows:
            raise ConnectorIngestionError("sync run does not belong to the connector instance")
        return dict(rows[0])

    @staticmethod
    def _as_json(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def _enforce_permissions(self, record: ConnectorRawRecord, context: Mapping[str, Any]) -> None:
        data_classes = set(self._as_json(context["data_classes"]) or ())
        if record.data_class not in data_classes:
            raise ConnectorPermissionDenied(f"connector does not declare data class {record.data_class!r}")
        definitions = {
            item["key"]: item for item in (self._as_json(context["permissions"]) or ())
        }
        required = set(record.required_permissions)
        required.update(key for key, item in definitions.items() if item.get("required"))
        unknown = required - definitions.keys()
        if unknown:
            raise ConnectorPermissionDenied(f"unknown connector permissions: {sorted(unknown)}")
        denied = {
            key for key in required
            if definitions[key].get("access") != PermissionAccess.READ.value
        }
        if denied:
            raise ConnectorPermissionDenied(f"permissions do not authorise acquisition: {sorted(denied)}")
        enabled = set(self._as_json(context["enabled_permissions"]) or ())
        missing = required - enabled
        if missing:
            raise ConnectorPermissionDenied(f"required connector permissions are disabled: {sorted(missing)}")

    async def _snapshot_for(self, context: Mapping[str, Any]) -> UUID:
        rows = await self.postgres.execute(
            """SELECT id FROM export_snapshots WHERE analysis_run_id=$1
            AND metadata->>'connector_instance_id'=$2 ORDER BY ingested_at,id LIMIT 1""",
            context["analysis_run_id"], str(context["connector_instance_id"]),
        )
        if rows:
            return rows[0]["id"]
        return await self.ledger.create_export_snapshot(
            context["analysis_run_id"], "manual_import", profile_id=context["profile_id"],
            controller_key=context["provider"], metadata={
                "acquisition": "source_connector", "bridge_version": BRIDGE_VERSION,
                "connector_instance_id": str(context["connector_instance_id"]),
                "connector_key": context["connector_key"],
                "definition_version": context["definition_version"],
            },
        )

    async def _validate_snapshot(self, snapshot_id: UUID, analysis_run_id: UUID) -> None:
        rows = await self.postgres.execute(
            "SELECT id FROM export_snapshots WHERE id=$1 AND analysis_run_id=$2",
            snapshot_id, analysis_run_id,
        )
        if not rows:
            raise ConnectorIngestionError("export snapshot does not belong to the sync run AnalysisRun")

    async def _claim_raw_record(self, record: ConnectorRawRecord, sync_run_id: UUID) -> Mapping[str, Any]:
        rows = await self.postgres.execute(
            """INSERT INTO connector_raw_records
            (connector_instance_id,sync_run_id,source_record_id,source_record_version,record_signature,
             data_class,occurred_at,observed_at,media_type,source_metadata,required_permissions,ingestion_status)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,'ingesting')
            ON CONFLICT(connector_instance_id,record_signature) DO UPDATE SET
              ingestion_status=CASE WHEN connector_raw_records.ingestion_status='failed'
                THEN 'ingesting' ELSE connector_raw_records.ingestion_status END,
              error=CASE WHEN connector_raw_records.ingestion_status='failed' THEN NULL
                ELSE connector_raw_records.error END
            RETURNING id,source_artifact_id,ingestion_status""",
            record.connector_instance_id, sync_run_id, record.source_record_id,
            record.source_record_version, record.record_signature, record.data_class,
            record.occurred_at, record.observed_at, record.media_type,
            _json(record.source_metadata), _json(record.required_permissions),
        )
        return rows[0]

    def _original_path(self, record: ConnectorRawRecord, context: Mapping[str, Any]) -> str:
        supplied = record.source_metadata.get("file_name") or record.source_metadata.get("path")
        name = _safe_component(Path(str(supplied)).name if supplied else record.source_record_id, fallback="record")
        extension = _extension_for(record)
        if not name.casefold().endswith(extension.casefold()):
            name += extension
        return "/".join((
            "connectors", _safe_component(str(context["connector_key"]), fallback="connector"),
            _safe_component(str(context["account_key"]), fallback="default"),
            _safe_component(record.source_record_version, fallback="1"),
            f"{record.record_signature[:16]}-{name}",
        ))

    async def _record_typed_artifact(self, record, context, snapshot_id, blob, original_path) -> UUID:
        existing = await self.postgres.execute(
            "SELECT id FROM source_artifacts WHERE export_snapshot_id=$1 AND original_path=$2 AND archive_member_path IS NULL",
            snapshot_id, original_path,
        )
        if existing:
            return existing[0]["id"]
        _, artifact_id = await self.ledger.record_source_occurrence(
            snapshot_id, blob.sha256, blob.byte_size, storage_uri=blob.path.resolve().as_uri(),
            original_path=original_path, file_name=Path(original_path).name,
            declared_mime=record.media_type, extension=_extension_for(record),
            file_type_status="declared", canonical_hash=blob.sha256,
            source_organisation=context["provider"], source_product=context["connector_key"],
            source_service=context["connector_type"],
        )
        return artifact_id

    async def _ensure_root_locator(self, artifact_id: UUID, record: ConnectorRawRecord) -> UUID:
        media_type = record.media_type.split(";", 1)[0].strip().casefold()
        if media_type == "application/json":
            locator_type, locator = LocatorType.JSON_POINTER, {"pointer": ""}
        else:
            locator_type, locator = LocatorType.TEXT_SPAN, {
                "byte_start": 0, "byte_end": len(record.payload),
            }
        rows = await self.postgres.execute(
            """SELECT id FROM evidence_locators WHERE artifact_id=$1 AND locator_type=$2
            AND locator=$3::jsonb AND verified ORDER BY created_at,id LIMIT 1""",
            artifact_id, locator_type.value, _json(locator),
        )
        if rows:
            return rows[0]["id"]
        return await self.ledger.create_locator(
            EvidenceLocatorCreate(
                artifact_id=artifact_id, locator_type=locator_type, locator=locator,
                expected_raw_hash=(hashlib.sha256(record.payload).hexdigest() if locator_type is LocatorType.TEXT_SPAN else None),
            ),
            record.payload,
        )

    async def _duplicate_result(self, raw, record: ConnectorRawRecord) -> ConnectorIngestionResult:
        artifact_id = raw["source_artifact_id"]
        rows = await self.postgres.execute(
            """SELECT sa.export_snapshot_id,es.analysis_run_id FROM source_artifacts sa
            JOIN export_snapshots es ON es.id=sa.export_snapshot_id WHERE sa.id=$1""", artifact_id,
        )
        if not rows:
            raise ConnectorIngestionError("ingested connector record is missing its SourceArtifact")
        locator_id = await self._ensure_root_locator(artifact_id, record)
        return ConnectorIngestionResult(
            raw_record_id=raw["id"], source_artifact_id=artifact_id,
            analysis_run_id=rows[0]["analysis_run_id"], export_snapshot_id=rows[0]["export_snapshot_id"],
            root_locator_id=locator_id, ingestion_status="ingested",
            duplicate=True,
        )
