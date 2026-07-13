"""Operational Task 3 event-lake to feature/temporal materialisation stage.

This module invokes the already-canonical deterministic analytical modules. It
does not create a second behavioural truth store: raw ActivityEvents remain in
Parquet and every persisted output cites those immutable event identifiers.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from typing import Iterable
from uuid import UUID

from features.classification import ServicePathDataClassDetector
from features.density import DensityCooccurrenceDetector
from features.geospatial import ExplicitInteractionFeatureDetector, GeospatialFeatureDetector
from features.identifiers import IdentifierFeatureDetector
from features.pipeline import extract_features
from ingestion.models import ActivityEvent, HistoryType, TemporalAggregate, TemporalState
from temporal.engagement import build_engagement_profile
from temporal.episodes import EvidenceSignalPoint, detect_project_episode_candidates
from temporal.eras import MonthlyFeatureVector, build_personal_eras
from temporal.routines import build_routine_distributions


DERIVATION_METHOD = "task3.deterministic-event-materialisation"
DERIVATION_VERSION = "1.0.0"


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _feature_key(candidate) -> str:
    payload = {
        "feature_type": candidate.feature_type,
        "detector_id": candidate.detector_id,
        "detector_version": candidate.detector_version,
        "source_event_ids": sorted(map(str, candidate.source_event_ids)),
        "source_artifact_ids": sorted(map(str, candidate.source_artifact_ids)),
        "calculated_values": candidate.calculated_values,
    }
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _window(events: tuple[ActivityEvent, ...]) -> tuple[datetime, datetime] | None:
    times = sorted(event.occurred_at for event in events if event.occurred_at is not None)
    if not times:
        return None
    start = times[0]
    end = times[-1] + timedelta(microseconds=1)
    return start, end


def _daily_points(events: tuple[ActivityEvent, ...], subject_id: str) -> tuple[EvidenceSignalPoint, ...]:
    buckets: dict[datetime, list[UUID]] = defaultdict(list)
    for event in events:
        if event.subject_id != subject_id or event.occurred_at is None:
            continue
        day = datetime.combine(event.occurred_at.date(), time.min, event.occurred_at.tzinfo or timezone.utc)
        buckets[day].append(event.event_id)
    return tuple(EvidenceSignalPoint(occurred_at=day, value=float(len(ids)), evidence_event_ids=tuple(sorted(ids, key=str))) for day, ids in sorted(buckets.items()))


def _monthly_vectors(events: tuple[ActivityEvent, ...], subject_id: str) -> tuple[MonthlyFeatureVector, ...]:
    buckets: dict[object, list[ActivityEvent]] = defaultdict(list)
    for event in events:
        if event.subject_id == subject_id and event.occurred_at is not None:
            buckets[event.occurred_at.date().replace(day=1)].append(event)
    result = []
    for month, rows in sorted(buckets.items()):
        result.append(MonthlyFeatureVector(
            month=month,
            dimensions={
                "event_count": float(len(rows)),
                "service_count": float(len({row.service for row in rows if row.service})),
                "investigation_count": float(sum(row.action_class.value == "SEARCHED" for row in rows)),
                "creation_count": float(sum(row.action_class.value in {"CREATED", "PUBLISHED"} for row in rows)),
                "implementation_count": float(sum(row.action_class.value in {"EDITED", "CODED"} for row in rows)),
            },
            evidence_event_ids=tuple(sorted((row.event_id for row in rows), key=str)),
        ))
    return tuple(result)


class OperationalTemporalMaterializer:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def materialize(
        self, *, analysis_run_id: UUID, partition_file_hash: str,
        events: Iterable[ActivityEvent], artifact_paths: dict[UUID, str] | None = None,
    ) -> dict[str, int | str]:
        rows = tuple(events)
        existing = await self.connection.fetchrow(
            """SELECT id,status,event_count,feature_count,aggregate_count,state_count
            FROM temporal_materialisation_runs
            WHERE analysis_run_id=$1 AND partition_file_hash=$2 AND derivation_version=$3""",
            analysis_run_id, partition_file_hash, DERIVATION_VERSION,
        )
        if existing and existing["status"] == "completed":
            return {"status":"completed","event_count":existing["event_count"],"feature_count":existing["feature_count"],
                    "aggregate_count":existing["aggregate_count"],"state_count":existing["state_count"]}
        materialisation_id = await self.connection.fetchval(
            """INSERT INTO temporal_materialisation_runs
            (analysis_run_id,partition_file_hash,derivation_method,derivation_version,status,event_count)
            VALUES($1,$2,$3,$4,'running',$5)
            ON CONFLICT(analysis_run_id,partition_file_hash,derivation_version) DO UPDATE
            SET status='running',error=NULL,started_at=NOW(),completed_at=NULL
            RETURNING id""",
            analysis_run_id, partition_file_hash, DERIVATION_METHOD, DERIVATION_VERSION, len(rows),
        )
        feature_count = aggregate_count = state_count = 0
        transaction = self.connection.transaction()
        transaction_started = False
        try:
            await transaction.start()
            transaction_started = True
            detectors = (
                ServicePathDataClassDetector(artifact_paths), IdentifierFeatureDetector(),
                GeospatialFeatureDetector(), ExplicitInteractionFeatureDetector(), DensityCooccurrenceDetector(),
            )
            extracted = extract_features(rows, detectors, analysis_run_id=analysis_run_id)
            for candidate in extracted.candidates:
                await self.connection.execute(
                    """INSERT INTO deterministic_feature_candidates
                    (materialisation_run_id,analysis_run_id,feature_key,feature_type,detector_id,detector_version,
                     candidate_status,calculated_values,confidence,rule_result,source_event_ids,source_artifact_ids)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11::jsonb,$12::jsonb)
                    ON CONFLICT(analysis_run_id,feature_key) DO NOTHING""",
                    materialisation_id, analysis_run_id, _feature_key(candidate), candidate.feature_type,
                    candidate.detector_id, candidate.detector_version, candidate.candidate_status.value,
                    _json(candidate.calculated_values), candidate.confidence, candidate.rule_result,
                    _json([str(value) for value in candidate.source_event_ids]),
                    _json([str(value) for value in candidate.source_artifact_ids]),
                )
            feature_count = len(extracted.candidates)

            window = _window(rows)
            if window:
                start, end = window
                for subject_id in sorted({event.subject_id for event in rows}):
                    subject_events = tuple(event for event in rows if event.subject_id == subject_id)
                    profile = build_engagement_profile(subject_events, subject_id=subject_id, window_start=start, window_end=end)
                    if profile:
                        aggregate = TemporalAggregate(
                            subject_id=subject_id, history_type=HistoryType.PERSONAL_BEHAVIOURAL,
                            aggregate_type="engagement_profile", aggregate_key="all-actions",
                            window_start=start, window_end=end,
                            values={name:getattr(profile,name) for name in ("consumption","investigation","creation","implementation","communication")},
                            source_event_count=len(profile.evidence_event_ids), detector_id="engagement.action-class",
                            detector_version=DERIVATION_VERSION,
                        )
                        await self._append_aggregate(materialisation_id, analysis_run_id, aggregate)
                        aggregate_count += 1
                        state = TemporalState(
                            subject_id=subject_id, history_type=HistoryType.PERSONAL_BEHAVIOURAL,
                            state_type="engagement_profile", state_key=f"{start.isoformat()}/{end.isoformat()}",
                            occurred_at=end, valid_from=start, valid_to=end,
                            system_asserted_at=datetime.now(timezone.utc),
                            dimensions={name:float(getattr(profile,name)) for name in ("consumption","investigation","creation","implementation","communication")},
                            evidence_event_ids=profile.evidence_event_ids,
                            detector_id="engagement.action-class", detector_version=DERIVATION_VERSION,
                        )
                        await self.connection.execute(
                            """INSERT INTO temporal_states
                            (analysis_run_id,subject_id,history_type,state_type,state_key,occurred_at,valid_from,valid_to,
                             system_asserted_at,dimensions,evidence_event_ids,detector_id,detector_version,materialisation_run_id)
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12,$13,$14)""",
                            analysis_run_id, state.subject_id, state.history_type.value, state.state_type,
                            state.state_key, state.occurred_at, state.valid_from, state.valid_to,
                            state.system_asserted_at, _json(state.dimensions),
                            _json([str(value) for value in state.evidence_event_ids]), state.detector_id,
                            state.detector_version, materialisation_id,
                        )
                        state_count += 1
                    for distribution in build_routine_distributions(subject_events, window_start=start, window_end=end):
                        aggregate = TemporalAggregate(
                            subject_id=subject_id, history_type=HistoryType.PERSONAL_BEHAVIOURAL,
                            aggregate_type="routine_distribution", aggregate_key=f"{distribution.dimension}:{distribution.bucket}",
                            window_start=start, window_end=end,
                            values={"event_count":distribution.event_count,"proportion":distribution.proportion},
                            source_event_count=len(distribution.evidence_event_ids), detector_id=distribution.detector_id,
                            detector_version=distribution.detector_version,
                        )
                        await self._append_aggregate(materialisation_id, analysis_run_id, aggregate)
                        aggregate_count += 1
                    for episode in detect_project_episode_candidates(_daily_points(rows, subject_id), subject_id=subject_id):
                        await self.connection.execute(
                            """INSERT INTO temporal_episodes
                            (id,analysis_run_id,subject_id,history_type,episode_kind,start_at,end_at,evidence_event_ids,
                             detector_id,detector_version,materialisation_run_id)
                            VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11) ON CONFLICT(id) DO NOTHING""",
                            episode.episode_id, analysis_run_id, episode.subject_id, episode.history_type.value,
                            episode.episode_kind.value, episode.start_at, episode.end_at,
                            _json([str(value) for value in episode.evidence_event_ids]), episode.detector_id,
                            episode.detector_version, materialisation_id,
                        )
                    era_analysis = build_personal_eras(_monthly_vectors(rows, subject_id), subject_id=subject_id)
                    for era in era_analysis.eras:
                        await self.connection.execute(
                            """INSERT INTO personal_eras
                            (id,analysis_run_id,subject_id,start_at,end_at,monthly_feature_vectors,change_point_indices,
                             evidence_event_ids,detector_id,detector_version,materialisation_run_id)
                            VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9,$10,$11) ON CONFLICT(id) DO NOTHING""",
                            era.era_id, analysis_run_id, era.subject_id, era.start_at, era.end_at,
                            _json(era.monthly_feature_vectors), _json(era.change_point_indices),
                            _json([str(value) for value in era.evidence_event_ids]), era.detector_id,
                            era.detector_version, materialisation_id,
                        )
            await self.connection.execute(
                """UPDATE temporal_materialisation_runs SET status='completed',feature_count=$2,
                aggregate_count=$3,state_count=$4,completed_at=NOW() WHERE id=$1""",
                materialisation_id, feature_count, aggregate_count, state_count,
            )
            await transaction.commit()
            transaction_started = False
            return {"status":"completed","event_count":len(rows),"feature_count":feature_count,
                    "aggregate_count":aggregate_count,"state_count":state_count}
        except Exception as exc:
            if transaction_started:
                await transaction.rollback()
            await self.connection.execute(
                "UPDATE temporal_materialisation_runs SET status='failed',error=$2::jsonb,completed_at=NOW() WHERE id=$1",
                materialisation_id, _json({"type":type(exc).__name__,"message":str(exc)}),
            )
            raise

    async def _append_aggregate(self, materialisation_id: UUID, analysis_run_id: UUID, aggregate: TemporalAggregate) -> None:
        await self.connection.execute(
            """INSERT INTO temporal_aggregates
            (analysis_run_id,subject_id,history_type,aggregate_type,aggregate_key,window_start,window_end,
             values,source_event_count,detector_id,detector_version,materialisation_run_id)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12)""",
            analysis_run_id, aggregate.subject_id, aggregate.history_type.value, aggregate.aggregate_type,
            aggregate.aggregate_key, aggregate.window_start, aggregate.window_end, _json(aggregate.values),
            aggregate.source_event_count, aggregate.detector_id, aggregate.detector_version, materialisation_id,
        )
