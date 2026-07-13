"""Deterministic feature orchestration and bounded semantic residue batching."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Protocol
from uuid import UUID

from ingestion.models import (
    ActivityEvent, FeatureCandidate, FeatureCandidateStatus, ModelAdjudicationBundle,
)
from ingestion.storage import read_parquet_polars


class FeatureDetector(Protocol):
    detector_id: str
    detector_version: str

    def detect(self, events: tuple[ActivityEvent, ...]) -> Iterable[FeatureCandidate]: ...


@dataclass(frozen=True, slots=True)
class FeatureExtractionResult:
    candidates: tuple[FeatureCandidate, ...]
    adjudication_bundles: tuple[ModelAdjudicationBundle, ...]
    event_count: int

    @property
    def model_invocation_count(self) -> int:
        return len(self.adjudication_bundles)


def load_activity_event_partitions(paths) -> tuple[ActivityEvent, ...]:
    """Load canonical event partitions without loading source artefact files."""
    rows = read_parquet_polars(paths).collect().to_dicts()
    decoded: list[ActivityEvent] = []
    for row in rows:
        values = dict(row)
        for field in ("object_value", "occurred_at_original", "identifiers", "locations", "relationships", "epistemic_hints", "field_locator_ids"):
            if isinstance(values.get(field), str):
                values[field] = json.loads(values[field])
        decoded.append(ActivityEvent.model_validate(values))
    return tuple(decoded)


def extract_partition_features(paths, detectors: Iterable[FeatureDetector], **kwargs) -> FeatureExtractionResult:
    return extract_features(load_activity_event_partitions(paths), detectors, **kwargs)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _residue_sample(candidate: FeatureCandidate, maximum_bytes: int) -> dict:
    sample = {
        "feature_type": candidate.feature_type,
        "detector_id": candidate.detector_id,
        "detector_version": candidate.detector_version,
        "candidate_status": candidate.candidate_status.value,
        "calculated_values": candidate.calculated_values,
        "confidence": candidate.confidence,
        "rule_result": candidate.rule_result,
        "source_event_ids": [str(value) for value in candidate.source_event_ids],
    }
    if len(_canonical(sample)) <= maximum_bytes:
        return sample
    values = _canonical(candidate.calculated_values)
    summary = {
        "feature_type": candidate.feature_type,
        "detector_id": candidate.detector_id,
        "detector_version": candidate.detector_version,
        "candidate_status": candidate.candidate_status.value,
        "calculated_values_omitted": True,
        "calculated_values_sha256": hashlib.sha256(values).hexdigest(),
        "calculated_value_keys": sorted(candidate.calculated_values)[:64],
        "source_event_count": len(candidate.source_event_ids),
    }
    if len(_canonical(summary)) > maximum_bytes:
        raise ValueError("maximum_sample_bytes is too small for a residue manifest")
    return summary


def extract_features(
    events: Iterable[ActivityEvent], detectors: Iterable[FeatureDetector], *,
    analysis_run_id: UUID, maximum_sample_bytes: int = 32_768,
    maximum_candidates_per_bundle: int = 64,
) -> FeatureExtractionResult:
    if maximum_sample_bytes < 512:
        raise ValueError("maximum_sample_bytes must be at least 512")
    if maximum_candidates_per_bundle < 1:
        raise ValueError("maximum_candidates_per_bundle must be positive")
    event_rows = tuple(events)
    event_ids = {event.event_id for event in event_rows}
    artifact_by_event = {event.event_id: event.artifact_id for event in event_rows}
    candidates: list[FeatureCandidate] = []
    for detector in detectors:
        for candidate in detector.detect(event_rows):
            if candidate.detector_id != detector.detector_id or candidate.detector_version != detector.detector_version:
                raise ValueError("detector output identity does not match the executing detector")
            if any(event_id not in event_ids for event_id in candidate.source_event_ids):
                raise ValueError("feature candidate refers to an event outside this extraction batch")
            candidates.append(candidate)
    candidates.sort(key=lambda item: (
        item.feature_type, item.detector_id, item.detector_version,
        tuple(map(str, item.source_event_ids)), _canonical(item.calculated_values),
    ))
    residue = [candidate for candidate in candidates if candidate.candidate_status in {
        FeatureCandidateStatus.AMBIGUOUS, FeatureCandidateStatus.ADJUDICATION_REQUIRED,
    }]
    bundles: list[ModelAdjudicationBundle] = []
    cursor = 0
    while cursor < len(residue):
        samples: list[dict] = []
        used = 2
        start = cursor
        while cursor < len(residue) and len(samples) < maximum_candidates_per_bundle:
            sample = _residue_sample(residue[cursor], maximum_sample_bytes)
            extra = len(_canonical(sample)) + (1 if samples else 0)
            if samples and used + extra > maximum_sample_bytes:
                break
            if not samples and used + extra > maximum_sample_bytes:
                raise ValueError("residue sample cannot fit the configured bundle")
            samples.append(sample)
            used += extra
            cursor += 1
        selected = residue[start:cursor]
        artifact_ids = sorted({
            artifact_id for candidate in selected
            for artifact_id in (*candidate.source_artifact_ids, *(artifact_by_event[event_id] for event_id in candidate.source_event_ids))
        }, key=str)
        bundles.append(ModelAdjudicationBundle(
            task_key="semantic.adjudication", analysis_run_id=analysis_run_id,
            source_artifact_ids=tuple(artifact_ids),
            purpose="Adjudicate only deterministic detector residue; do not promote unsupported semantics.",
            samples=tuple(samples), maximum_sample_bytes=maximum_sample_bytes,
            omitted_record_count=0,
        ))
    return FeatureExtractionResult(
        candidates=tuple(candidates), adjudication_bundles=tuple(bundles),
        event_count=len(event_rows),
    )
