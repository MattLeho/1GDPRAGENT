"""Frozen Task 3 temporal-analysis contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from ingestion.models import FrozenModel, HistoryType


class TemporalAxes(FrozenModel):
    occurred_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    controller_observed_from: datetime | None = None
    controller_observed_to: datetime | None = None
    exported_at: datetime | None = None
    ingested_at: datetime | None = None
    system_asserted_at: datetime | None = None
    superseded_at: datetime | None = None

    @model_validator(mode="after")
    def ordered_ranges(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to precedes valid_from")
        if self.controller_observed_from and self.controller_observed_to and self.controller_observed_to < self.controller_observed_from:
            raise ValueError("controller_observed_to precedes controller_observed_from")
        return self


class TopicAssignment(FrozenModel):
    topic_id: str
    topic_path: tuple[str, ...] = Field(min_length=1)
    source_event_ids: tuple[UUID, ...] = Field(min_length=1)
    assignment_method: str
    assignment_version: str
    confidence: float = Field(ge=0, le=1)


class SixDimensionalInterestState(FrozenModel):
    subject_id: str
    history_type: HistoryType = HistoryType.PERSONAL_BEHAVIOURAL
    topic_id: str
    topic_path: tuple[str, ...] = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    intensity: float = Field(ge=0)
    persistence: float = Field(ge=0)
    recurrence: float = Field(ge=0)
    breadth: float = Field(ge=0)
    novelty: float = Field(ge=0)
    context_dispersion: float = Field(ge=0)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    detector_id: str
    detector_version: str

    @model_validator(mode="after")
    def valid_window(self):
        if self.window_end < self.window_start:
            raise ValueError("window_end precedes window_start")
        return self


class WeightedInterestView(FrozenModel):
    state: SixDimensionalInterestState
    weights: dict[str, float]
    weighted_value: float
    configuration_id: str
    derived: bool = True


class EpisodeKind(str, Enum):
    PROJECT = "ProjectEpisodeCandidate"
    TOPIC_CLUSTER = "TopicClusterEpisodeCandidate"


class EpisodeCandidate(FrozenModel):
    episode_id: UUID
    episode_kind: EpisodeKind
    subject_id: str
    history_type: HistoryType = HistoryType.PERSONAL_BEHAVIOURAL
    start_at: datetime
    end_at: datetime
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    detector_id: str
    detector_version: str
    machine_label: str | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.end_at < self.start_at:
            raise ValueError("episode end precedes start")
        return self


class EngagementProfile(FrozenModel):
    subject_id: str
    window_start: datetime
    window_end: datetime
    consumption: float = Field(ge=0)
    investigation: float = Field(ge=0)
    creation: float = Field(ge=0)
    implementation: float = Field(ge=0)
    communication: float = Field(ge=0)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)


class RoutineDistribution(FrozenModel):
    subject_id: str
    window_start: datetime
    window_end: datetime
    dimension: str = Field(pattern=r"^(hour|day|service|event|topic)$")
    bucket: str
    event_count: int = Field(ge=0)
    proportion: float = Field(ge=0, le=1)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    detector_id: str
    detector_version: str


class RoutineDrift(FrozenModel):
    subject_id: str
    dimension: str = Field(pattern=r"^(hour|day|service|event|topic)$")
    baseline_start: datetime
    baseline_end: datetime
    current_start: datetime
    current_end: datetime
    baseline_distribution: dict[str, float]
    current_distribution: dict[str, float]
    total_variation_distance: float = Field(ge=0, le=1)
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    detector_id: str
    detector_version: str


class InteractionState(FrozenModel):
    subject_id: str
    counterpart_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    inbound: int = Field(ge=0)
    outbound: int = Field(ge=0)
    reciprocity_ratio: float | None = Field(default=None, ge=0)
    response_interval_seconds: float | None = Field(default=None, ge=0)
    active_days: int = Field(ge=0)
    service_count: int = Field(ge=0)
    burstiness: float | None = None
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    relationship_label: None = None
    personality_label: None = None


class PersonalEraCandidate(FrozenModel):
    era_id: UUID
    subject_id: str
    start_at: datetime
    end_at: datetime
    monthly_feature_vectors: tuple[dict[str, float], ...] = Field(min_length=1)
    change_point_indices: tuple[int, ...]
    evidence_event_ids: tuple[UUID, ...] = Field(min_length=1)
    detector_id: str
    detector_version: str
    machine_label: str | None = None
    human_label: str | None = None


class DeltaStatus(str, Enum):
    NEW = "NEW"
    REMOVED_FROM_EXPORT = "REMOVED_FROM_EXPORT"
    UNCHANGED = "UNCHANGED"
    MODIFIED = "MODIFIED"


class DriftType(str, Enum):
    PERSONAL = "PERSONAL_DRIFT"
    CONTROLLER = "CONTROLLER_DRIFT"
    UNDERSTANDING = "UNDERSTANDING_DRIFT"


class SnapshotDelta(FrozenModel):
    entity_type: str
    entity_key: str
    before_snapshot_id: UUID
    after_snapshot_id: UUID
    status: DeltaStatus
    drift_type: DriftType
    before_value: Any | None = None
    after_value: Any | None = None
    interpretation: str = "newly observed by this system"
