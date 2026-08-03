"""End-to-end local-first deterministic ingestion orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Any, Iterable
from uuid import UUID,uuid4

from db.postgres import PostgresClient, get_postgres_client
from evidence.ledger import EvidenceLedger
from request_domain import RequestRepository

from .catalogue import record_ingestion_status
from .checkpoints import CheckpointStore
from .events import catalogue_observations, catalogue_partition, write_activity_events
from .materialization import OperationalTemporalMaterializer
from .models import (
    CheckpointStatus, ExtractionContext, PipelineStage, QuarantineStatus,
    ReviewStatus, SupportStatus,
)
from .parser_runtime import (
    LocatedRecord, execute_parser, parser_selectors, selector_to_json_pointer,
)
from .processor import LocalFileProcessor, ProcessedFile
from .registry import FORMATS_BY_KEY
from .schema_registry import SchemaRegistry, SchemaResolution
from .storage import StorageRoots, write_raw_blob


PIPELINE_VERSION = "task3-local-first-v1"


@dataclass(frozen=True, slots=True)
class SpecialistTaskRequest:
    request_id: UUID
    task_key: str
    input_manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BulkProcessResult:
    analysis_run_id: UUID
    export_snapshot_id: UUID
    artifact_id: UUID
    content_hash: str
    detected_format: str | None
    support_status: str | None
    ingestion_status: str
    extraction_unit_count: int
    fingerprint_id: str | None
    schema_outcome: str | None
    interpretation_request_id: UUID | None
    event_count: int
    specialist_tasks: tuple[SpecialistTaskRequest, ...]
    warnings: tuple[str, ...]


def allowed_import_roots() -> tuple[Path, ...]:
    configured = os.environ.get("GDPR_IMPORT_ROOTS", "/source-uploads")
    return tuple(Path(value).expanduser().resolve(strict=False) for value in configured.split(os.pathsep) if value)


def resolve_import_path(path: str | os.PathLike[str], roots: Iterable[Path] | None = None) -> Path:
    source = Path(path).expanduser().resolve(strict=True)
    permitted = tuple(roots or allowed_import_roots())
    if not source.is_file():
        raise ValueError("import source must be a regular file")
    if not any(source.is_relative_to(root) for root in permitted):
        raise ValueError("import source is outside configured read-only roots")
    return source


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _file_type_status(processed: ProcessedFile) -> str:
    return {
        "MATCH": "matched", "MISMATCH": "mismatch",
        "AMBIGUOUS": "unknown", "UNKNOWN": "unknown",
    }[processed.truth.status.value]


def _source_identity(source: Path) -> dict[str, Any]:
    """Cheap restart guard; ctime/mtime/inode prevent stale completed-manifest reuse."""
    stat = source.stat()
    return {
        "resolved_path": str(source),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "ctime_ns": stat.st_ctime_ns,
        "device": stat.st_dev,
        "inode": stat.st_ino,
    }


def _result_manifest(result: BulkProcessResult) -> dict[str, Any]:
    return {
        **{name: str(getattr(result, name)) for name in (
            "analysis_run_id", "export_snapshot_id", "artifact_id",
        )},
        "content_hash": result.content_hash,
        "detected_format": result.detected_format,
        "support_status": result.support_status,
        "ingestion_status": result.ingestion_status,
        "extraction_unit_count": result.extraction_unit_count,
        "fingerprint_id": result.fingerprint_id,
        "schema_outcome": result.schema_outcome,
        "interpretation_request_id": str(result.interpretation_request_id) if result.interpretation_request_id else None,
        "event_count": result.event_count,
        "specialist_tasks": [
            {"request_id": str(task.request_id), "task_key": task.task_key, "input_manifest": task.input_manifest}
            for task in result.specialist_tasks
        ],
        "warnings": list(result.warnings),
    }


def _result_from_manifest(manifest: dict[str, Any]) -> BulkProcessResult:
    return BulkProcessResult(
        analysis_run_id=UUID(manifest["analysis_run_id"]),
        export_snapshot_id=UUID(manifest["export_snapshot_id"]),
        artifact_id=UUID(manifest["artifact_id"]),
        content_hash=manifest["content_hash"],
        detected_format=manifest.get("detected_format"),
        support_status=manifest.get("support_status"),
        ingestion_status=manifest["ingestion_status"],
        extraction_unit_count=int(manifest["extraction_unit_count"]),
        fingerprint_id=manifest.get("fingerprint_id"),
        schema_outcome=manifest.get("schema_outcome"),
        interpretation_request_id=(UUID(manifest["interpretation_request_id"]) if manifest.get("interpretation_request_id") else None),
        event_count=int(manifest["event_count"]),
        specialist_tasks=tuple(
            SpecialistTaskRequest(UUID(task["request_id"]), task["task_key"], dict(task["input_manifest"]))
            for task in manifest.get("specialist_tasks", ())
        ),
        warnings=tuple(manifest.get("warnings", ())),
    )


def _member_lineage_path(member) -> str:
    message = member.metadata.get("message")
    part = member.metadata.get("part")
    if message is not None and part is not None:
        return f"message-{message}/part-{part}/{Path(member.member_path).name}"
    return f"member-{member.ordinal}/{member.member_path}"


class BulkIngestionService:
    def __init__(
        self, postgres: PostgresClient | None = None, *, roots: StorageRoots | None = None,
        import_roots: Iterable[Path] | None = None, processor: LocalFileProcessor | None = None,
    ) -> None:
        self.postgres = postgres or get_postgres_client()
        self.requests = RequestRepository(self.postgres)
        self.ledger = EvidenceLedger(self.postgres)
        self.roots = (roots or StorageRoots.from_env()).ensure()
        self.import_roots = tuple(import_roots or allowed_import_roots())
        self.processor = processor or LocalFileProcessor()

    async def prepare_run(
        self, *, request_id: UUID | None = None, profile_id: UUID | None = None,
        source_type: str = "manual_import", controller_key: str | None = None,
        exported_at=None, configuration: dict[str, Any] | None = None,
    ) -> tuple[UUID, UUID]:
        run_id = await self.ledger.create_analysis_run(
            "bulk_ingestion", PIPELINE_VERSION, request_id=request_id,
            profile_id=profile_id, configuration=configuration or {},
        )
        snapshot_id = await self.ledger.create_export_snapshot(
            run_id, source_type, request_id=request_id, profile_id=profile_id,
            controller_key=controller_key, exported_at=exported_at,
            metadata={"pipeline_version": PIPELINE_VERSION},
        )
        return run_id, snapshot_id

    async def process_file(
        self, path: str, *, analysis_run_id: UUID, export_snapshot_id: UUID,
        declared_mime: str | None = None, original_path: str | None = None,
        requested_tasks: Iterable[str] = (), received_data_id: UUID | None = None,
    ) -> BulkProcessResult:
        source = resolve_import_path(path, self.import_roots)
        item_key = original_path or source.name
        source_identity = _source_identity(source)
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection:
            checkpoints = CheckpointStore(connection)
            inventory = await checkpoints.begin(
                analysis_run_id=analysis_run_id, stage=PipelineStage.INVENTORY,
                item_key=item_key,
            )
            completed_manifest = inventory.progress.get("completed_result")
            if (
                inventory.status is CheckpointStatus.COMPLETED
                and inventory.progress.get("source_identity") == source_identity
                and isinstance(completed_manifest, dict)
            ):
                replay = _result_from_manifest(completed_manifest)
                if replay.analysis_run_id == analysis_run_id and replay.export_snapshot_id == export_snapshot_id:
                    return replay
            if inventory.status is not CheckpointStatus.COMPLETED:
                inventory = await checkpoints.finish(
                    inventory, progress={"bytes": source.stat().st_size, "files": 1, "source_identity": source_identity},
                )

            hashing = await checkpoints.begin(
                analysis_run_id=analysis_run_id, stage=PipelineStage.HASHING,
                item_key=item_key,
            )
            with source.open("rb") as handle:
                blob = write_raw_blob(self.roots.blobs, handle)
            await checkpoints.finish(hashing, progress={"content_hash": blob.sha256, "bytes": blob.byte_size})

        existing = await self.postgres.execute(
            """SELECT sa.id,cb.sha256 FROM source_artifacts sa JOIN content_blobs cb ON cb.id=sa.content_blob_id
            WHERE sa.export_snapshot_id=$1 AND sa.original_path=$2 ORDER BY sa.created_at LIMIT 1""",
            export_snapshot_id,item_key,
        )
        is_new=not existing
        if existing:
            if existing[0]["sha256"]!=blob.sha256:
                raise ValueError("source path changed content within one export snapshot")
            artifact_id=existing[0]["id"]
        else:
            artifact_id=uuid4()

        context = ExtractionContext(
            artifact_id=artifact_id, analysis_run_id=analysis_run_id,
            export_snapshot_id=export_snapshot_id, source_path=str(source),
        )
        async with pool.acquire() as connection:
            checkpoints = CheckpointStore(connection)
            typing = await checkpoints.begin(
                analysis_run_id=analysis_run_id, stage=PipelineStage.FILE_TYPING,
                item_key=str(artifact_id), content_hash=blob.sha256,
            )
            processed = self.processor.process(source, context, declared_mime=declared_mime)
            await checkpoints.finish(typing, progress={
                "truth": processed.truth.status.value,
                "detected_format": processed.truth.detected_format,
                "dispatch": processed.dispatch.status,
            })
        fingerprint_db_id=None
        if processed.fingerprint is not None:
            async with pool.acquire() as connection:
                fingerprint_db_id=await SchemaRegistry(connection).ensure_fingerprint(
                    fingerprint_hash=processed.fingerprint.fingerprint_id,
                    family=processed.fingerprint.family,
                    provider_id=processed.fingerprint.provider_id,
                    provider_version=processed.fingerprint.provider_version,
                    canonical_shape=processed.fingerprint.canonical_shape,
                    sample_count=processed.fingerprint.sample_count,
                )
        if is_new:
            await self.ledger.record_source_occurrence(
                export_snapshot_id, blob.sha256, blob.byte_size,
                storage_uri=blob.path.resolve().as_uri(), original_path=item_key,
                file_name=source.name, declared_mime=declared_mime,
                detected_mime=processed.truth.detected_mime,
                extension="".join(source.suffixes).lower() or None,
                file_type_status=_file_type_status(processed),
                canonical_hash=processed.canonical_sha256 or processed.raw_sha256,
                artifact_id=artifact_id,structure_fingerprint_id=fingerprint_db_id,
            )

        extraction = processed.extraction
        warnings = tuple((extraction.warnings if extraction else ()))
        if processed.dispatch.status != "selected":
            ingestion_status = "ambiguous" if processed.dispatch.status == "ambiguous" else "unsupported"
        elif extraction and extraction.quarantine_status is not QuarantineStatus.NONE:
            ingestion_status = "quarantined"
        else:
            ingestion_status = "completed"
        support = processed.dispatch.support
        await record_ingestion_status(
            self.postgres, artifact_id=artifact_id, analysis_run_id=analysis_run_id,
            status=ingestion_status, support_status=support.status.value if support else None,
            detected_format=(extraction.detected_format if extraction else processed.truth.detected_format),
            adapter_id=(extraction.adapter_id if extraction else None),
            adapter_version=(extraction.adapter_version if extraction else None),
            quarantine_reason=(extraction.quarantine_status.value if extraction and extraction.quarantine_status is not QuarantineStatus.NONE else None),
            next_action=("review" if ingestion_status in {"ambiguous", "quarantined", "unsupported"} else "fingerprint"),
            warnings=warnings,
        )

        unit_locator_ids: dict[str, UUID] = {}
        if extraction is not None:
            async with pool.acquire() as connection:
                checkpoints = CheckpointStore(connection)
                stage = await checkpoints.begin(
                    analysis_run_id=analysis_run_id, stage=PipelineStage.FAMILY_EXTRACTION,
                    item_key=str(artifact_id), content_hash=blob.sha256,
                )
            existing_units=await self.postgres.execute(
                """SELECT unit_key,evidence_locator_id FROM extraction_units
                WHERE analysis_run_id=$1 AND artifact_id=$2 AND adapter_id=$3 AND adapter_version=$4""",
                analysis_run_id,artifact_id,extraction.adapter_id,extraction.adapter_version,
            )
            existing_locators={row["unit_key"]:row["evidence_locator_id"] for row in existing_units}
            for unit in extraction.units:
                locator_id = existing_locators.get(unit.unit_id)
                if locator_id is None:
                    locator_id = await self.ledger.create_unverified_locator(
                        artifact_id, unit.evidence_locator.locator_type,
                        unit.evidence_locator.locator,
                    )
                unit_locator_ids[unit.unit_id] = locator_id
                await self.postgres.execute(
                    """INSERT INTO extraction_units
                    (analysis_run_id,artifact_id,unit_key,unit_type,ordinal,parent_unit_key,text_value,
                     scalar_value,structured_payload,metadata,evidence_locator_id,adapter_id,adapter_version)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12,$13)
                    ON CONFLICT(analysis_run_id,artifact_id,adapter_id,adapter_version,unit_key) DO NOTHING""",
                    analysis_run_id, artifact_id, unit.unit_id, unit.unit_type,
                    unit.ordinal, unit.parent_unit_id, unit.text,
                    _json(unit.value) if unit.value is not None else None,
                    _json(unit.structured_payload) if unit.structured_payload is not None else None,
                    _json(unit.metadata), locator_id, extraction.adapter_id, extraction.adapter_version,
                )
            for member in extraction.embedded_members:
                if member.content is None:
                    continue
                lineage_path = _member_lineage_path(member)
                child_rows = await self.postgres.execute(
                    """SELECT id,parent_artifact_id FROM source_artifacts
                    WHERE export_snapshot_id=$1 AND original_path=$2 AND archive_member_path=$3""",
                    export_snapshot_id, item_key, lineage_path,
                )
                if child_rows:
                    if child_rows[0]["parent_artifact_id"] != artifact_id:
                        raise ValueError("embedded member lineage conflicts with an existing source artifact")
                    continue
                child_blob = write_raw_blob(self.roots.blobs, member.content)
                await self.ledger.record_source_occurrence(
                    export_snapshot_id, child_blob.sha256, child_blob.byte_size,
                    storage_uri=child_blob.path.resolve().as_uri(),
                    original_path=item_key, file_name=Path(member.member_path).name,
                    parent_artifact_id=artifact_id, archive_member_path=lineage_path,
                    declared_mime=member.media_type, detected_mime=member.media_type,
                    extension="".join(Path(member.member_path).suffixes).lower() or None,
                    file_type_status="declared" if member.media_type else "unknown",
                    canonical_hash=child_blob.sha256,
                )
            async with pool.acquire() as connection:
                await CheckpointStore(connection).finish(stage, progress={
                    "units": len(extraction.units), "embedded_members": len(extraction.embedded_members),
                    "quarantine_status": extraction.quarantine_status.value,
                }, status=(CheckpointStatus.QUARANTINED if extraction.quarantine_status is not QuarantineStatus.NONE else CheckpointStatus.COMPLETED))

        resolution: SchemaResolution | None = None
        event_count = 0
        if processed.fingerprint is not None and extraction is not None:
            records = [
                unit.structured_payload for unit in extraction.units
                if unit.unit_type == "record" and isinstance(unit.structured_payload, dict)
            ]
            async with pool.acquire() as connection:
                checkpoints = CheckpointStore(connection)
                fingerprint_stage = await checkpoints.begin(
                    analysis_run_id=analysis_run_id, stage=PipelineStage.FINGERPRINTING,
                    item_key=str(artifact_id), content_hash=blob.sha256,
                )
                registry = SchemaRegistry(connection)
                resolution = await registry.resolve(
                    processed.fingerprint, records, analysis_run_id=analysis_run_id,
                    source_artifact_ids=(artifact_id,),
                )
                await checkpoints.finish(fingerprint_stage, progress={
                    "fingerprint_id": processed.fingerprint.fingerprint_id,
                    "schema_outcome": resolution.outcome,
                })
            if resolution.outcome == "known" and resolution.approved is not None:
                event_count = await self._execute_known_parser(
                    processed, resolution, extraction, unit_locator_ids,
                    analysis_run_id=analysis_run_id, export_snapshot_id=export_snapshot_id,
                    artifact_id=artifact_id, content_hash=blob.sha256,
                )

        specialist = await self._specialist_requests(
            analysis_run_id, artifact_id, source, declared_mime,
            support.task_routes if support else (), requested_tasks,
            received_data_id=received_data_id,
        )
        if received_data_id is not None:
            await self.requests.update_received_processing(
                received_data_id, analysis_run_id,
                status="completed" if ingestion_status == "completed" and not specialist else ("processing" if specialist else "error"),
                processing_stage="specialist_tasks" if specialist else ingestion_status,
                processing_progress=80 if specialist else 100,
                error_message=None if ingestion_status == "completed" else processed.dispatch.reason,
            )
        result = BulkProcessResult(
            analysis_run_id=analysis_run_id, export_snapshot_id=export_snapshot_id,
            artifact_id=artifact_id, content_hash=blob.sha256,
            detected_format=(extraction.detected_format if extraction else processed.truth.detected_format),
            support_status=support.status.value if support else None,
            ingestion_status=ingestion_status,
            extraction_unit_count=len(extraction.units) if extraction else 0,
            fingerprint_id=processed.fingerprint.fingerprint_id if processed.fingerprint else None,
            schema_outcome=resolution.outcome if resolution else None,
            interpretation_request_id=(resolution.interpretation.request_id if resolution and resolution.interpretation else None),
            event_count=event_count, specialist_tasks=specialist, warnings=warnings,
        )
        async with pool.acquire() as connection:
            await CheckpointStore(connection).finish(
                inventory,
                progress={
                    "bytes": source_identity["size"], "files": 1,
                    "source_identity": source_identity,
                    "completed_result": _result_manifest(result),
                },
            )
        return result

    async def _execute_known_parser(
        self, processed, resolution, extraction, unit_locator_ids, *, analysis_run_id,
        export_snapshot_id, artifact_id, content_hash,
    ) -> int:
        spec = resolution.approved.spec
        selectors = parser_selectors(spec)
        records: list[LocatedRecord] = []
        for unit in extraction.units:
            if unit.unit_type != "record" or not isinstance(unit.structured_payload, dict):
                continue
            field_ids: dict[str, UUID] = {}
            for selector in selectors.values():
                pointer = selector_to_json_pointer(selector, family=spec.file_family)
                base = unit.evidence_locator
                if base.locator_type == "json_record":
                    locator_type = "json_record"
                    locator = {"record": base.locator["record"], "pointer": pointer}
                else:
                    locator_type = "json_pointer"
                    prefix = str(base.locator.get("pointer", ""))
                    locator = {"pointer": prefix + pointer}
                field_ids[selector] = await self.ledger.create_unverified_locator(
                    artifact_id, locator_type, locator,
                )
            records.append(LocatedRecord(
                value=unit.structured_payload,
                source_locator_id=unit_locator_ids[unit.unit_id], field_locator_ids=field_ids,
            ))
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection:
            checkpoints = CheckpointStore(connection)
            stage = await checkpoints.begin(
                analysis_run_id=analysis_run_id, stage=PipelineStage.PARSING,
                item_key=str(artifact_id), content_hash=content_hash,
                parser_version=spec.parser_version,
            )
        parsed = execute_parser(
            spec, records, artifact_id=artifact_id,
            export_snapshot_id=export_snapshot_id,
        )
        if parsed.events:
            written = write_activity_events(
                self.roots.event_lake, parsed.events, analysis_run_id=analysis_run_id,
                partition_key=f"{artifact_id}-{spec.parser_id}-{spec.parser_version}",
            )
            signatures = {event.event_id: event.record_signature for event in written.events}
            async with pool.acquire() as connection, connection.transaction():
                await catalogue_partition(connection, written.event_partition, partition_key=f"events/{artifact_id}")
                await catalogue_partition(connection, written.observation_partition, partition_key=f"observations/{artifact_id}")
                await catalogue_observations(connection, written.observations, signatures)
            async with pool.acquire() as connection:
                checkpoints = CheckpointStore(connection)
                feature_stage = await checkpoints.begin(
                    analysis_run_id=analysis_run_id, stage=PipelineStage.FEATURE_EXTRACTION,
                    item_key=str(artifact_id), content_hash=content_hash,
                    parser_version=spec.parser_version,
                )
                temporal_stage = await checkpoints.begin(
                    analysis_run_id=analysis_run_id, stage=PipelineStage.TEMPORAL_AGGREGATION,
                    item_key=str(artifact_id), content_hash=content_hash,
                    parser_version=spec.parser_version,
                )
                materialized = await OperationalTemporalMaterializer(connection).materialize(
                    analysis_run_id=analysis_run_id,
                    partition_file_hash=written.event_partition.file_hash,
                    events=written.events,
                    artifact_paths={artifact_id: processed.path.name},
                )
                await checkpoints.finish(feature_stage, progress={
                    "events":materialized["event_count"], "features":materialized["feature_count"],
                })
                await checkpoints.finish(temporal_stage, progress={
                    "aggregates":materialized["aggregate_count"], "states":materialized["state_count"],
                })
        async with pool.acquire() as connection:
            await CheckpointStore(connection).finish(
                stage, status=(CheckpointStatus.COMPLETED if not parsed.rejected_records else CheckpointStatus.FAILED),
                progress={"records_seen": parsed.records_seen, "events_emitted": parsed.events_emitted,
                          "rejected_records": parsed.rejected_records},
                error=({"warnings": parsed.warnings} if parsed.rejected_records else None),
            )
        return parsed.events_emitted

    async def _specialist_requests(
        self, analysis_run_id: UUID, artifact_id: UUID, source: Path,
        declared_mime: str | None, supported: Iterable[str], requested: Iterable[str],
        *, received_data_id: UUID | None = None,
    ) -> tuple[SpecialistTaskRequest, ...]:
        requested_set = set(requested)
        allowed = set(supported)
        invalid = requested_set - allowed
        if invalid:
            raise ValueError(f"specialist tasks are not supported for this format: {sorted(invalid)}")
        result: list[SpecialistTaskRequest] = []
        for task_key in sorted(requested_set):
            rows = await self.postgres.execute(
                """INSERT INTO specialist_task_requests(analysis_run_id,artifact_id,task_key,input_manifest)
                VALUES($1,$2,$3,$4::jsonb) ON CONFLICT(analysis_run_id,artifact_id,task_key)
                DO UPDATE SET task_key=EXCLUDED.task_key RETURNING id,input_manifest""",
                analysis_run_id, artifact_id, task_key,
                _json({"file_path": str(source), "mime_type": declared_mime,
                       "received_data_id": str(received_data_id) if received_data_id else None}),
            )
            manifest = rows[0]["input_manifest"]
            result.append(SpecialistTaskRequest(
                request_id=rows[0]["id"], task_key=task_key,
                input_manifest=json.loads(manifest) if isinstance(manifest, str) else dict(manifest),
            ))
        return tuple(result)
