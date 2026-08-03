"""Read and persist versioned Personal Insights materialisations.

ActivityEvent rows remain in Parquet.  PostgreSQL is used only to discover
overlapping partitions, read accepted/derived evidence, and cache immutable
versioned insight payloads and their evidence index.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Iterable
from uuid import UUID

from features.pipeline import load_activity_event_partitions
from ingestion.models import ActivityEvent
from insights.models import InsightEvidenceRef, InsightPeriod


def _decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class EventPartition:
    partition_id: UUID
    analysis_run_id: UUID
    storage_uri: str
    file_hash: str
    min_occurred_at: datetime | None
    max_occurred_at: datetime | None
    row_count: int


class InsightRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def dependency_tokens(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[str, ...]:
        """Version non-Parquet sources that can change a derived snapshot."""
        queries = (
            ("assertions", "SELECT count(*)::bigint AS count,max(system_asserted_at) AS changed FROM assertions WHERE status='accepted' AND subject_ref=$1 AND (valid_to IS NULL OR valid_to>$2) AND (valid_from IS NULL OR valid_from<$3)"),
            ("states", "SELECT count(*)::bigint AS count,max(system_asserted_at) AS changed FROM temporal_states WHERE subject_id=$1 AND (valid_to IS NULL OR valid_to>$2) AND (valid_from IS NULL OR valid_from<$3)"),
            ("aggregates", "SELECT count(*)::bigint AS count,max(created_at) AS changed FROM temporal_aggregates WHERE subject_id=$1 AND (window_end IS NULL OR window_end>$2) AND (window_start IS NULL OR window_start<$3)"),
            ("topics", "SELECT count(*)::bigint AS count,max(created_at) AS changed FROM temporal_topic_assignments WHERE $1::text IS NOT NULL AND $2::timestamptz IS NOT NULL AND $3::timestamptz IS NOT NULL"),
            ("episodes", "SELECT count(*)::bigint AS count,max(created_at) AS changed FROM temporal_episodes WHERE subject_id=$1 AND end_at>=$2 AND start_at<$3"),
            ("eras", "SELECT count(*)::bigint AS count,max(created_at) AS changed FROM personal_eras WHERE subject_id=$1 AND end_at>=$2 AND start_at<$3"),
            ("media", "SELECT count(*)::bigint AS count,max(ml.created_at) AS changed FROM media_location_candidates ml JOIN source_artifacts sa ON sa.id=ml.artifact_id JOIN export_snapshots es ON es.id=sa.export_snapshot_id WHERE es.profile_id::text=$1 AND (ml.occurred_at IS NULL OR (ml.occurred_at>=$2 AND ml.occurred_at<$3))"),
            ("specialist_media", "SELECT count(*)::bigint AS count,max(sr.completed_at) AS changed FROM specialist_task_requests sr JOIN source_artifacts sa ON sa.id=sr.artifact_id JOIN export_snapshots es ON es.id=sa.export_snapshot_id WHERE es.profile_id::text=$1 AND $2::timestamptz IS NOT NULL AND $3::timestamptz IS NOT NULL AND sr.status='completed' AND sr.task_key IN ('image.origin_classification','image.ocr','image.caption','image.landmark_candidate')"),
            ("context", "SELECT count(*)::bigint AS count,max(ingested_at) AS changed FROM external_context_events WHERE $1::text IS NOT NULL AND occurred_at<$3 AND (ended_at IS NULL OR ended_at>$2)"),
        )
        tokens=[]
        for name,query in queries:
            row=await self.connection.fetchrow(query,subject_id,from_at,to_at)
            tokens.append(f"{name}:{int(row['count'])}:{row['changed'].isoformat() if row['changed'] else '-'}")
        return tuple(tokens)

    async def discover_event_partitions(
        self, *, from_at: datetime, to_at: datetime,
        analysis_run_ids: Iterable[UUID] = (),
    ) -> tuple[EventPartition, ...]:
        """Return only event partitions whose recorded bounds overlap [from,to)."""
        if to_at <= from_at:
            raise ValueError("to_at must be after from_at")
        run_ids = tuple(analysis_run_ids)
        rows = await self.connection.fetch(
            """SELECT id,analysis_run_id,storage_uri,file_hash,min_occurred_at,
                      max_occurred_at,row_count
               FROM event_partitions
               WHERE schema_version='activity-event-v1'
                 AND (max_occurred_at IS NULL OR max_occurred_at >= $1)
                 AND (min_occurred_at IS NULL OR min_occurred_at < $2)
                 AND (cardinality($3::uuid[])=0 OR analysis_run_id=ANY($3::uuid[]))
               ORDER BY min_occurred_at NULLS FIRST,storage_uri,id""",
            from_at, to_at, list(run_ids),
        )
        return tuple(EventPartition(
            partition_id=row["id"], analysis_run_id=row["analysis_run_id"],
            storage_uri=row["storage_uri"], file_hash=row["file_hash"],
            min_occurred_at=row["min_occurred_at"], max_occurred_at=row["max_occurred_at"],
            row_count=int(row["row_count"]),
        ) for row in rows)

    def load_activity_events(
        self, partitions: Iterable[EventPartition], *, subject_id: str,
        from_at: datetime, to_at: datetime,
    ) -> tuple[ActivityEvent, ...]:
        """Load selected partitions once and deduplicate logical events."""
        paths = tuple(partition.storage_uri for partition in partitions)
        if not paths:
            return ()
        selected: dict[str, ActivityEvent] = {}
        for event in load_activity_event_partitions(paths):
            if event.subject_id != subject_id or event.occurred_at is None:
                continue
            if not from_at <= event.occurred_at < to_at:
                continue
            current = selected.get(event.record_signature)
            if current is not None and current.event_id != event.event_id:
                raise ValueError("record signature maps to conflicting event IDs")
            selected[event.record_signature] = event
        return tuple(sorted(selected.values(), key=lambda row: (row.occurred_at, str(row.event_id))))

    async def read_accepted_assertions(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT a.* FROM assertions a
               WHERE a.status='accepted' AND a.subject_ref=$1
                 AND (a.valid_to IS NULL OR a.valid_to>$2)
                 AND (a.valid_from IS NULL OR a.valid_from<$3)
               ORDER BY a.system_asserted_at,a.id""", subject_id, from_at, to_at,
        )
        return tuple(dict(row) for row in rows)

    async def read_temporal_states(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT * FROM temporal_states WHERE subject_id=$1
                 AND (valid_to IS NULL OR valid_to>$2)
                 AND (valid_from IS NULL OR valid_from<$3)
               ORDER BY history_type,state_type,state_key,system_asserted_at""",
            subject_id, from_at, to_at,
        )
        return tuple({**dict(row), "dimensions": _decode(row["dimensions"]),
                      "evidence_event_ids": _decode(row["evidence_event_ids"])} for row in rows)

    async def read_episode_candidates(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT * FROM temporal_episodes WHERE subject_id=$1 AND end_at>=$2 AND start_at<$3
               ORDER BY start_at,id""", subject_id, from_at, to_at,
        )
        return tuple({**dict(row), "evidence_event_ids": _decode(row["evidence_event_ids"])} for row in rows)

    async def read_personal_eras(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT era.*,machine.label AS machine_label,human.label AS human_label
               FROM personal_eras era
               LEFT JOIN LATERAL (SELECT label FROM personal_era_labels WHERE era_id=era.id AND label_source='machine' ORDER BY created_at DESC LIMIT 1) machine ON TRUE
               LEFT JOIN LATERAL (SELECT label FROM personal_era_labels WHERE era_id=era.id AND label_source='human' ORDER BY created_at DESC LIMIT 1) human ON TRUE
               WHERE era.subject_id=$1 AND era.end_at>=$2 AND era.start_at<$3
               ORDER BY era.start_at,era.id""", subject_id, from_at, to_at,
        )
        return tuple(dict(row) for row in rows)

    async def read_topic_assignments(self, event_ids: Iterable[UUID]) -> tuple[dict[str, Any], ...]:
        wanted = {str(value) for value in event_ids}
        if not wanted:
            return ()
        rows = await self.connection.fetch(
            """SELECT * FROM temporal_topic_assignments
               WHERE source_event_ids ?| $1::text[] ORDER BY created_at,id""", sorted(wanted),
        )
        return tuple({**dict(row), "topic_path": _decode(row["topic_path"]),
                      "source_event_ids": _decode(row["source_event_ids"])} for row in rows)

    async def read_temporal_aggregates(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT * FROM temporal_aggregates WHERE subject_id=$1
               AND (window_end IS NULL OR window_end>$2)
               AND (window_start IS NULL OR window_start<$3)
               ORDER BY aggregate_type,aggregate_key,window_start,id""", subject_id, from_at, to_at,
        )
        return tuple({**dict(row), "values": _decode(row["values"])} for row in rows)

    async def read_external_context_events(self, *, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT * FROM external_context_events
               WHERE occurred_at<$2 AND (ended_at IS NULL OR ended_at>$1)
               ORDER BY occurred_at,id""", from_at, to_at,
        )
        return tuple({**dict(row), "topics": _decode(row["topics"])} for row in rows)

    async def read_media_location_candidates(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT ml.*,el.artifact_id AS locator_artifact_id
               FROM media_location_candidates ml
               JOIN evidence_locators el ON el.id=ml.evidence_locator_id
               JOIN source_artifacts sa ON sa.id=ml.artifact_id
               JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.profile_id::text=$1
                 AND (ml.occurred_at IS NULL OR (ml.occurred_at>=$2 AND ml.occurred_at<$3))
               ORDER BY ml.occurred_at NULLS LAST,ml.id""", subject_id, from_at, to_at,
        )
        return tuple(dict(row) for row in rows)

    async def read_export_deltas(self, *, subject_id: str, from_at: datetime, to_at: datetime) -> tuple[dict[str, Any], ...]:
        rows = await self.connection.fetch(
            """SELECT delta.* FROM export_snapshot_deltas delta
               JOIN analysis_runs run ON run.id=delta.analysis_run_id
               WHERE run.profile_id::text=$1
                 AND delta.created_at>=$2 AND delta.created_at<$3
               ORDER BY delta.created_at,delta.id""", subject_id, from_at, to_at,
        )
        return tuple({**dict(row), "before_value": _decode(row["before_value"]),
                      "after_value": _decode(row["after_value"])} for row in rows)

    async def cached_payload(self, cache_key: str, derivation_version: str) -> dict[str, Any] | None:
        row = await self.connection.fetchrow(
            "SELECT id,payload,created_at FROM insight_materialisations WHERE cache_key=$1 AND derivation_version=$2",
            cache_key, derivation_version,
        )
        if row is None:
            return None
        return {"materialisation_id": row["id"], "payload": _decode(row["payload"]), "created_at": row["created_at"]}

    async def persist_materialisation(
        self, *, subject_id: str, period: InsightPeriod, module_key: str,
        cache_key: str, partition_hashes: Iterable[str], payload: dict[str, Any],
        derivation_method: str, derivation_version: str,
        analysis_run_id: UUID | None = None,
        compare_from_at: datetime | None = None, compare_to_at: datetime | None = None,
    ) -> UUID:
        """Insert once; an existing cache identity is never overwritten."""
        row = await self.connection.fetchrow(
            """INSERT INTO insight_materialisations
               (subject_id,analysis_run_id,temporal_mode,granularity,from_at,to_at,point_at,
                compare_from_at,compare_to_at,module_key,cache_key,source_partition_hashes,payload,
                derivation_method,derivation_version)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb,$14,$15)
               ON CONFLICT(cache_key,derivation_version) DO NOTHING RETURNING id,payload""",
            subject_id, analysis_run_id, period.mode.value, period.granularity.value,
            period.from_at, period.to_at, period.point_at, compare_from_at, compare_to_at,
            module_key, cache_key, json.dumps(sorted(set(partition_hashes))),
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
            derivation_method, derivation_version,
        )
        if row is not None:
            return row["id"]
        existing = await self.connection.fetchrow(
            "SELECT id,payload FROM insight_materialisations WHERE cache_key=$1 AND derivation_version=$2",
            cache_key, derivation_version,
        )
        if existing is None or _decode(existing["payload"]) != payload:
            raise ValueError("immutable materialisation cache collision")
        return existing["id"]

    async def persist_evidence_index(self, materialisation_id: UUID, insight_id: UUID, evidence: Iterable[InsightEvidenceRef]) -> int:
        rows = tuple(evidence)
        for item in rows:
            await self.connection.execute(
                """INSERT INTO insight_evidence_index
                   (insight_id,materialisation_id,evidence_kind,evidence_ref_id,role,artifact_id,locator_id,occurred_at,weight)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING""",
                insight_id, materialisation_id, item.kind.value, item.ref_id, item.role,
                item.artifact_id, item.locator_id, item.occurred_at, item.weight,
            )
        return len(rows)

    async def persist_insight_catalogue(self, materialisation_id: UUID, item) -> None:
        window_start=getattr(item,"window_start",None) or getattr(item,"start_at",None)
        window_end=getattr(item,"window_end",None) or getattr(item,"end_at",None)
        await self.connection.execute(
            """INSERT INTO insight_catalogue
               (materialisation_id,insight_id,detector_id,detector_version,analysis_run_id,
                window_start,window_end,evidence_count)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT DO NOTHING""",
            materialisation_id,item.insight_id,item.detector_id,item.detector_version,
            item.analysis_run_id,window_start,window_end,len(item.evidence),
        )

    async def persist_aggregate_buckets(
        self, materialisation_id: UUID, *, subject_id: str, granularity: str,
        aggregate_type: str, aggregate_key: str, buckets: Iterable[dict[str, Any]],
    ) -> int:
        rows = tuple(buckets)
        for bucket in rows:
            evidence_ids = tuple(str(value) for value in bucket.get("evidence_event_ids", ()))
            await self.connection.execute(
                """INSERT INTO insight_aggregate_buckets
                   (materialisation_id,subject_id,granularity,bucket_start,bucket_end,
                    aggregate_type,aggregate_key,values,evidence_event_ids,source_event_count)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10)
                   ON CONFLICT DO NOTHING""",
                materialisation_id, subject_id, granularity, bucket["start_at"], bucket["end_at"],
                aggregate_type, aggregate_key,
                json.dumps(bucket.get("values", {}), sort_keys=True, separators=(",", ":")),
                json.dumps(evidence_ids), len(evidence_ids),
            )
        return len(rows)

    async def previous_aggregate_buckets(
        self, *, subject_id: str, period: InsightPeriod, module_key: str,
        derivation_version: str, exclude_cache_key: str,
        aggregate_type: str, aggregate_key: str,
        compare_from_at: datetime | None = None,
        compare_to_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Read the newest compatible immutable bucket set before a rebuild.

        Exact period/comparison matching prevents reuse across temporal views.
        Per-bucket source hashes, rather than the materialisation-wide dependency
        token list, are used by the service to detect additions and removals.
        """
        rows = await self.connection.fetch(
            """WITH previous AS (
                   SELECT id FROM insight_materialisations
                   WHERE subject_id=$1 AND temporal_mode=$2 AND granularity=$3
                     AND from_at IS NOT DISTINCT FROM $4::timestamptz
                     AND to_at IS NOT DISTINCT FROM $5::timestamptz
                     AND point_at IS NOT DISTINCT FROM $6::timestamptz
                     AND compare_from_at IS NOT DISTINCT FROM $7::timestamptz
                     AND compare_to_at IS NOT DISTINCT FROM $8::timestamptz
                     AND module_key=$9 AND derivation_version=$10
                     AND cache_key<>$11
                   ORDER BY created_at DESC,id DESC LIMIT 1
               )
               SELECT p.id AS materialisation_id,b.bucket_start,b.bucket_end,
                      b.values,b.evidence_event_ids,b.source_event_count
               FROM previous p
               JOIN insight_aggregate_buckets b ON b.materialisation_id=p.id
               WHERE b.aggregate_type=$12 AND b.aggregate_key=$13
               ORDER BY b.bucket_start""",
            subject_id, period.mode.value, period.granularity.value,
            period.from_at, period.to_at, period.point_at,
            compare_from_at, compare_to_at, module_key, derivation_version,
            exclude_cache_key, aggregate_type, aggregate_key,
        )
        if not rows:
            return None
        return {
            "materialisation_id": rows[0]["materialisation_id"],
            "buckets": tuple({
                "start_at": row["bucket_start"], "end_at": row["bucket_end"],
                "values": _decode(row["values"]),
                "evidence_event_ids": _decode(row["evidence_event_ids"]),
                "source_event_count": int(row["source_event_count"]),
            } for row in rows),
        }
