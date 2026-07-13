"""Deterministic monthly-feature segmentation into personal-era candidates."""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite, sqrt
from statistics import median
from typing import Literal, Mapping, Sequence, TypeVar
from uuid import UUID, uuid5

from pydantic import Field, model_validator

from ingestion.models import FrozenModel
from temporal.episodes import detect_change_points_pelt
from temporal.models import PersonalEraCandidate


ERA_NAMESPACE = UUID("444e4753-8b80-508a-93e1-909d8ba9b725")
_LabelT = TypeVar("_LabelT")


class MonthlyFeatureVector(FrozenModel):
    """Evidence-linked deterministic features for one calendar month."""

    month: date
    dimensions: dict[str, float] = Field(min_length=1)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def canonical_month_and_values(self):
        if self.month.day != 1:
            raise ValueError("month must be the first calendar day")
        if any(not key for key in self.dimensions):
            raise ValueError("feature dimension names cannot be empty")
        if any(not isfinite(value) for value in self.dimensions.values()):
            raise ValueError("monthly features must be finite")
        return self


class EvidenceConstrainedMachineLabel(FrozenModel):
    label: str = Field(min_length=1, max_length=512)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    execution_record_id: UUID
    labelling_method: str = Field(min_length=1)
    labelling_version: str = Field(min_length=1)


class HumanEraLabel(FrozenModel):
    label: str = Field(min_length=1, max_length=512)
    labelled_by: str = Field(min_length=1)


class EraLabelAssignment(FrozenModel):
    era_id: UUID
    label_source: Literal["machine", "human"]
    label: str
    evidence_event_ids: tuple[UUID, ...] = ()
    execution_record_id: UUID | None = None
    labelled_by: str | None = None

    @model_validator(mode="after")
    def source_specific_provenance(self):
        if self.label_source == "machine":
            if self.execution_record_id is None or not self.evidence_event_ids:
                raise ValueError("machine labels require execution and evidence provenance")
            if self.labelled_by is not None:
                raise ValueError("machine labels cannot carry human reviewer provenance")
        else:
            if self.labelled_by is None:
                raise ValueError("human labels require labelled_by")
            if self.execution_record_id is not None:
                raise ValueError("human labels cannot carry an execution record")
        return self


class EraAnalysis(FrozenModel):
    subject_id: str
    change_point_indices: tuple[int, ...]
    eras: tuple[PersonalEraCandidate, ...]
    label_assignments: tuple[EraLabelAssignment, ...] = ()


def _next_month(month: date) -> date:
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def _standardised_matrix(
    vectors: Sequence[MonthlyFeatureVector], dimensions: Sequence[str]
) -> list[list[float]]:
    columns = [
        [float(vector.dimensions.get(dimension, 0.0)) for vector in vectors]
        for dimension in dimensions
    ]
    scales: list[tuple[float, float]] = []
    for column in columns:
        centre = float(median(column))
        mad = float(median(abs(value - centre) for value in column))
        scale = 1.4826 * mad
        if scale == 0:
            variance = sum((value - centre) ** 2 for value in column) / len(column)
            scale = sqrt(variance)
        scales.append((centre, scale or 1.0))
    return [
        [
            (float(vector.dimensions.get(dimension, 0.0)) - scales[index][0])
            / scales[index][1]
            for index, dimension in enumerate(dimensions)
        ]
        for vector in vectors
    ]


def _contiguous_runs(vectors: Sequence[MonthlyFeatureVector]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(vectors)):
        if vectors[index].month != _next_month(vectors[index - 1].month):
            runs.append((start, index))
            start = index
    runs.append((start, len(vectors)))
    return runs


def _normalise_label_mapping(
    labels: Mapping[int, _LabelT] | None, *, era_count: int, label_kind: str
) -> Mapping[int, _LabelT]:
    result = labels or {}
    invalid = sorted(index for index in result if index < 0 or index >= era_count)
    if invalid:
        raise ValueError(f"{label_kind} label indices are outside the era range: {invalid}")
    return result


def build_personal_eras(
    vectors: Sequence[MonthlyFeatureVector],
    *,
    subject_id: str,
    penalty: float = 3.0,
    minimum_segment_size: int = 2,
    detector_id: str = "personal-era.monthly-pelt",
    detector_version: str = "1.0.0",
    machine_labels: Mapping[int, EvidenceConstrainedMachineLabel] | None = None,
    human_labels: Mapping[int, HumanEraLabel] | None = None,
) -> EraAnalysis:
    """Detect change points and cluster each contiguous period into an era.

    Machine labels must cite event evidence already contained by their era.
    Human labels travel through a distinct input and a distinct model field;
    neither label is copied into or used as a fallback for the other.
    """

    if not subject_id:
        raise ValueError("subject_id is required")
    if not vectors:
        return EraAnalysis(
            subject_id=subject_id, change_point_indices=(), eras=(), label_assignments=()
        )
    ordered = sorted(vectors, key=lambda item: item.month)
    if list(vectors) != ordered:
        raise ValueError("monthly feature vectors must be ordered by month")
    if len({item.month for item in vectors}) != len(vectors):
        raise ValueError("monthly feature vectors must have unique months")

    dimensions = tuple(sorted({key for vector in vectors for key in vector.dimensions}))
    matrix = _standardised_matrix(vectors, dimensions)
    boundaries: set[int] = set()
    for run_start, run_end in _contiguous_runs(vectors):
        if run_start:
            boundaries.add(run_start)  # missing calendar months force a new era
        relative = detect_change_points_pelt(
            matrix[run_start:run_end],
            penalty=penalty,
            minimum_segment_size=minimum_segment_size,
        )
        boundaries.update(run_start + index for index in relative)

    change_points = tuple(sorted(boundaries))
    segment_starts = (0, *change_points)
    segment_ends = (*change_points, len(vectors))
    machines = _normalise_label_mapping(
        machine_labels, era_count=len(segment_starts), label_kind="machine"
    )
    humans = _normalise_label_mapping(
        human_labels, era_count=len(segment_starts), label_kind="human"
    )

    eras: list[PersonalEraCandidate] = []
    label_assignments: list[EraLabelAssignment] = []
    for ordinal, (start, end) in enumerate(zip(segment_starts, segment_ends)):
        segment = vectors[start:end]
        evidence = tuple(
            sorted(
                {event_id for vector in segment for event_id in vector.evidence_event_ids},
                key=str,
            )
        )
        machine = machines.get(ordinal)
        if machine is not None and not set(machine.evidence_event_ids).issubset(evidence):
            raise ValueError(
                f"machine label {ordinal} cites evidence outside its era"
            )
        human = humans.get(ordinal)
        start_at = datetime.combine(segment[0].month, datetime.min.time(), timezone.utc)
        # end_at is an exclusive month boundary, so neighbouring eras remain
        # exactly contiguous without inventing sub-month precision.
        end_at = datetime.combine(_next_month(segment[-1].month), datetime.min.time(), timezone.utc)
        identity = "|".join(
            (
                subject_id,
                segment[0].month.isoformat(),
                segment[-1].month.isoformat(),
                detector_id,
                detector_version,
                *(str(event_id) for event_id in evidence),
            )
        )
        candidate = PersonalEraCandidate(
            era_id=uuid5(ERA_NAMESPACE, identity),
            subject_id=subject_id,
            start_at=start_at,
            end_at=end_at,
            monthly_feature_vectors=tuple(dict(vector.dimensions) for vector in segment),
            change_point_indices=change_points,
            evidence_event_ids=evidence,
            detector_id=detector_id,
            detector_version=detector_version,
            machine_label=None if machine is None else machine.label,
            human_label=None if human is None else human.label,
        )
        eras.append(candidate)
        if machine is not None:
            label_assignments.append(
                EraLabelAssignment(
                    era_id=candidate.era_id,
                    label_source="machine",
                    label=machine.label,
                    evidence_event_ids=machine.evidence_event_ids,
                    execution_record_id=machine.execution_record_id,
                )
            )
        if human is not None:
            label_assignments.append(
                EraLabelAssignment(
                    era_id=candidate.era_id,
                    label_source="human",
                    label=human.label,
                    labelled_by=human.labelled_by,
                )
            )
    return EraAnalysis(
        subject_id=subject_id,
        change_point_indices=change_points,
        eras=tuple(eras),
        label_assignments=tuple(label_assignments),
    )
