"""Canonical ActivityEvent partitioning and observation preservation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable
from uuid import UUID, uuid4

from .models import ActivityEvent, ActivityEventObservation, EventPartitionRecord
from .storage import PartitionMetadata, write_parquet_partition


EVENT_SCHEMA_VERSION = "activity-event-v1"
OBSERVATION_SCHEMA_VERSION = "activity-event-observation-v1"


@dataclass(frozen=True, slots=True)
class EventWriteResult:
    events: tuple[ActivityEvent, ...]
    observations: tuple[ActivityEventObservation, ...]
    event_partition: EventPartitionRecord
    observation_partition: EventPartitionRecord


def deduplicate_events(events: Iterable[ActivityEvent], *, observed_at: datetime | None = None) -> tuple[tuple[ActivityEvent, ...], tuple[ActivityEventObservation, ...]]:
    when = observed_at or datetime.now(timezone.utc)
    logical: dict[str, ActivityEvent] = {}
    observations: dict[tuple[UUID, UUID, UUID, UUID], ActivityEventObservation] = {}
    for event in events:
        existing = logical.get(event.record_signature)
        if existing is not None and existing.event_id != event.event_id:
            raise ValueError("one record signature must map to one deterministic event_id")
        logical.setdefault(event.record_signature, event)
        observation = ActivityEventObservation(
            event_id=event.event_id, export_snapshot_id=event.export_snapshot_id,
            artifact_id=event.artifact_id, source_locator_id=event.source_locator_id,
            observed_at=when,
        )
        key = (observation.event_id, observation.export_snapshot_id, observation.artifact_id, observation.source_locator_id)
        observations[key] = observation
    return (
        tuple(sorted(logical.values(), key=lambda item: (item.record_signature, str(item.event_id)))),
        tuple(sorted(observations.values(), key=lambda item: (str(item.event_id), str(item.export_snapshot_id), str(item.artifact_id), str(item.source_locator_id)))),
    )


def _serialise(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _rows(items) -> list[dict]:
    rows = [json.loads(item.model_dump_json()) for item in items]
    for row in rows:
        # Keep a stable scalar Parquet schema even when JSON objects are empty or
        # have different keys between event types.
        if "object_value" in row:
            row["object_value"] = json.dumps(row["object_value"], sort_keys=True, separators=(",", ":"), ensure_ascii=False) if row["object_value"] is not None else None
        if "occurred_at_original" in row:
            row["occurred_at_original"] = json.dumps(row["occurred_at_original"], sort_keys=True, separators=(",", ":"), ensure_ascii=False) if row["occurred_at_original"] is not None else None
        for field in ("identifiers", "locations", "relationships", "epistemic_hints", "field_locator_ids"):
            if field in row:
                row[field] = json.dumps(row[field], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return rows


def _partition_record(analysis_run_id: UUID, metadata: PartitionMetadata) -> EventPartitionRecord:
    return EventPartitionRecord(
        partition_id=uuid4(), analysis_run_id=analysis_run_id, path=str(metadata.path),
        file_hash=metadata.file_hash, schema_version=metadata.schema_version,
        row_count=metadata.row_count, min_occurred_at=metadata.min_occurred_at,
        max_occurred_at=metadata.max_occurred_at, byte_size=metadata.byte_size,
    )


def write_activity_events(
    root: str | Path, events: Iterable[ActivityEvent], *, analysis_run_id: UUID,
    partition_key: str, observed_at: datetime | None = None,
) -> EventWriteResult:
    logical, observations = deduplicate_events(events, observed_at=observed_at)
    if not logical:
        raise ValueError("at least one event is required")
    safe_key = partition_key.replace("\\", "_").replace("/", "_").replace("..", "_")
    if not safe_key or safe_key in {".", "_"}:
        raise ValueError("partition_key is invalid")
    base = Path(root) / str(analysis_run_id)
    event_meta = write_parquet_partition(
        base / "events" / f"{safe_key}.parquet", _rows(logical),
        schema_version=EVENT_SCHEMA_VERSION,
    )
    observation_meta = write_parquet_partition(
        base / "observations" / f"{safe_key}.parquet", _rows(observations),
        schema_version=OBSERVATION_SCHEMA_VERSION, time_column="observed_at",
    )
    return EventWriteResult(
        events=logical, observations=observations,
        event_partition=_partition_record(analysis_run_id, event_meta),
        observation_partition=_partition_record(analysis_run_id, observation_meta),
    )


async def catalogue_partition(connection, record: EventPartitionRecord, *, partition_key: str) -> UUID:
    """Idempotently register an atomic partition after its file write succeeds."""
    return await connection.fetchval(
        """WITH inserted AS (INSERT INTO event_partitions
        (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT(analysis_run_id,partition_key,file_hash) DO NOTHING RETURNING id)
        SELECT id FROM inserted UNION ALL SELECT id FROM event_partitions
        WHERE analysis_run_id=$2 AND partition_key=$3 AND file_hash=$5 LIMIT 1""",
        record.partition_id, record.analysis_run_id, partition_key, record.path,
        record.file_hash, record.schema_version, record.row_count,
        record.min_occurred_at, record.max_occurred_at, record.byte_size,
    )


async def catalogue_observations(connection, observations: Iterable[ActivityEventObservation], signatures: dict[UUID, str]) -> None:
    for item in observations:
        await connection.execute(
            """INSERT INTO logical_event_signatures(record_signature,event_id)
            VALUES($1,$2) ON CONFLICT(record_signature) DO NOTHING""",
            signatures[item.event_id], item.event_id,
        )
        await connection.execute(
            """INSERT INTO activity_event_observations
            (event_id,export_snapshot_id,artifact_id,source_locator_id,record_signature,observed_at)
            VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING""",
            item.event_id, item.export_snapshot_id, item.artifact_id,
            item.source_locator_id, signatures[item.event_id], item.observed_at,
        )
