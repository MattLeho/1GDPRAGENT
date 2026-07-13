"""Frozen Task 4 contracts.

The models in this module are derived views over ActivityEvents, accepted
Assertions and Task 3 temporal outputs. They never become a mutable generic
truth store for a person's interests or identity.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ingestion.models import FrozenModel, HistoryType


class TemporalMode(str, Enum):
    POINT_IN_TIME = "point_in_time"
    PERIOD = "period"
    COMPARE = "compare"


class PeriodGranularity(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class SignalClass(str, Enum):
    AMBIENT_EXPOSURE = "AMBIENT_EXPOSURE"
    PASSIVE_CONSUMPTION = "PASSIVE_CONSUMPTION"
    ACTIVE_INVESTIGATION = "ACTIVE_INVESTIGATION"
    CREATION = "CREATION"
    IMPLEMENTATION = "IMPLEMENTATION"
    COMMUNICATION = "COMMUNICATION"
    DISENGAGEMENT = "DISENGAGEMENT"
    UNKNOWN = "UNKNOWN"


class ConversationTurnRole(str, Enum):
    USER_AUTHORED_TURN = "USER_AUTHORED_TURN"
    ASSISTANT_GENERATED_TURN = "ASSISTANT_GENERATED_TURN"
    SYSTEM_TURN = "SYSTEM_TURN"
    TOOL_TURN = "TOOL_TURN"
    UNKNOWN = "UNKNOWN"


class CorrelationStatus(str, Enum):
    COINCIDENCE_CANDIDATE = "coincidence_candidate"
    POSSIBLE_RELATION = "possible_relation"
    EVIDENCE_SUPPORTED_RELATION = "evidence_supported_relation"
    USER_CONFIRMED = "user_confirmed"
    REJECTED = "rejected"


class MediaAnalysisMode(str, Enum):
    METADATA_ONLY = "metadata_only"
    SELECTIVE_VISUAL = "selective_visual"
    FULL_VISUAL = "full_visual"


class MediaOrigin(str, Enum):
    CAMERA_ORIGIN = "camera_origin"
    SCREENSHOT = "screenshot"
    DOWNLOADED_MEDIA = "downloaded_media"
    EDITED_MEDIA = "edited_media"
    GENERATED_MEDIA = "generated_media"
    UNKNOWN = "unknown"


class LocationBasis(str, Enum):
    EXIF_GPS = "exif_gps"
    TAKEOUT_SIDECAR = "takeout_sidecar"
    VISUAL_LANDMARK = "visual_landmark"
    USER_CONFIRMED = "user_confirmed"


class LocationEvidenceClass(str, Enum):
    STRONG_OBSERVATION = "strong_observation"
    CANDIDATE = "candidate"
    USER_CONFIRMED = "user_confirmed"
    REJECTED = "rejected"


class EvidenceKind(str, Enum):
    ACTIVITY_EVENT = "activity_event"
    ASSERTION = "assertion"
    TEMPORAL_STATE = "temporal_state"
    TEMPORAL_AGGREGATE = "temporal_aggregate"
    SOURCE_ARTIFACT = "source_artifact"
    EVIDENCE_LOCATOR = "evidence_locator"
    EXTERNAL_CONTEXT_EVENT = "external_context_event"
    MEDIA_LOCATION_CANDIDATE = "media_location_candidate"


class InsightPeriod(FrozenModel):
    mode: TemporalMode
    granularity: PeriodGranularity
    from_at: datetime | None = None
    to_at: datetime | None = None
    point_at: datetime | None = None

    @model_validator(mode="after")
    def valid_selection(self):
        if self.mode is TemporalMode.POINT_IN_TIME:
            if self.point_at is None or self.from_at is not None or self.to_at is not None:
                raise ValueError("point_in_time requires only point_at")
        else:
            if self.from_at is None or self.to_at is None or self.point_at is not None:
                raise ValueError("period/compare selections require from_at and to_at")
            if self.to_at <= self.from_at:
                raise ValueError("to_at must be after from_at")
        return self


class InsightComparisonPeriod(FrozenModel):
    current: InsightPeriod
    baseline: InsightPeriod

    @model_validator(mode="after")
    def period_modes(self):
        if self.current.mode is TemporalMode.POINT_IN_TIME or self.baseline.mode is TemporalMode.POINT_IN_TIME:
            raise ValueError("compare periods must be bounded periods")
        return self


class InsightEvidenceRef(FrozenModel):
    kind: EvidenceKind
    ref_id: UUID
    role: Literal["supporting", "exposure", "comparison", "contradicting", "user_confirmation"] = "supporting"
    occurred_at: datetime | None = None
    artifact_id: UUID | None = None
    locator_id: UUID | None = None
    label: str | None = None
    weight: float | None = Field(default=None, ge=0)


class DerivedInsight(FrozenModel):
    insight_id: UUID
    detector_id: str
    detector_version: str
    analysis_run_id: UUID | None = None
    calculated_features: dict[str, Any] = Field(default_factory=dict)
    evidence: tuple[InsightEvidenceRef, ...] = ()
    model_explanation: str | None = None


class ActivityDensityBin(FrozenModel):
    start_at: datetime
    end_at: datetime
    event_count: int = Field(ge=0)
    evidence_event_ids: tuple[UUID, ...] = ()


class TopicExposureState(DerivedInsight):
    topic_id: str
    topic_path: tuple[str, ...] = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    ambient_exposure_count: int = Field(ge=0)
    passive_consumption_count: int = Field(ge=0)
    active_investigation_count: int = Field(ge=0)
    creation_count: int = Field(ge=0)
    implementation_count: int = Field(ge=0)
    communication_count: int = Field(ge=0)
    interest_contributing_event_ids: tuple[UUID, ...] = ()


class ObservedInterestState(DerivedInsight):
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
    first_observed_at: datetime
    latest_observed_at: datetime
    peak_at: datetime | None = None
    source_domains: tuple[str, ...] = ()
    change: Literal["emerging", "returning", "continuing", "declining", "one_off"]
    previous_period_dimensions: dict[str, float] = Field(default_factory=dict)
    comparison_delta: dict[str, float] = Field(default_factory=dict)
    controller_profile_comparison: tuple[dict[str, Any], ...] = ()


class InsightEngagementProfile(DerivedInsight):
    subject_id: str
    window_start: datetime
    window_end: datetime
    ambient_exposure: float = Field(ge=0)
    passive_consumption: float = Field(ge=0)
    active_investigation: float = Field(ge=0)
    creation: float = Field(ge=0)
    implementation: float = Field(ge=0)
    communication: float = Field(ge=0)
    disengagement: float = Field(ge=0)
    comparison_delta: dict[str, float] = Field(default_factory=dict)


class InvestigationEpisodeCandidate(DerivedInsight):
    subject_id: str
    start_at: datetime
    end_at: datetime
    query_count: int = Field(ge=1)
    recurrence: int = Field(ge=0)
    domain_diversity: int = Field(ge=0)
    refinement_depth: int = Field(ge=0)
    cross_source_count: int = Field(ge=0)
    project_transition: bool = False
    topic_labels: tuple[str, ...] = ()
    status: Literal["candidate", "accepted", "rejected"] = "candidate"


class SearchInsight(DerivedInsight):
    recurring_queries: tuple[dict[str, Any], ...] = ()
    emerging_clusters: tuple[dict[str, Any], ...] = ()
    refinement_chains: tuple[dict[str, Any], ...] = ()
    abandoned_one_offs: int = Field(ge=0)
    episodes: tuple[InvestigationEpisodeCandidate, ...] = ()


class AIConversationInsight(DerivedInsight):
    user_originated_topics: tuple[dict[str, Any], ...] = ()
    sustained_clusters: tuple[dict[str, Any], ...] = ()
    recurrent_questions: tuple[dict[str, Any], ...] = ()
    refinement_chains: tuple[dict[str, Any], ...] = ()
    services: tuple[str, ...] = ()
    session_count: int = Field(ge=0)
    user_turn_count: int = Field(ge=0)
    assistant_turn_count: int = Field(ge=0)
    maximum_follow_up_depth: int = Field(ge=0)
    project_linked_session_ids: tuple[str, ...] = ()


class MediaLocationCandidate(DerivedInsight):
    artifact_id: UUID
    occurred_at: datetime | None = None
    temporal_precision: str
    location_type: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    place_label: str | None = None
    basis: LocationBasis
    confidence: float = Field(ge=0, le=1)
    evidence_class: LocationEvidenceClass
    media_origin: MediaOrigin
    reviewed_by: str | None = None

    @model_validator(mode="after")
    def presence_guard(self):
        if self.media_origin in {MediaOrigin.SCREENSHOT, MediaOrigin.DOWNLOADED_MEDIA, MediaOrigin.GENERATED_MEDIA} and self.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION:
            raise ValueError("screenshots, downloads and generated media cannot establish physical presence")
        if self.basis is LocationBasis.VISUAL_LANDMARK and self.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION:
            raise ValueError("visual landmarks remain candidates until human review")
        return self


class MediaContentCandidate(DerivedInsight):
    artifact_id: UUID
    evidence_locator_id: UUID
    media_origin: MediaOrigin
    ocr_word_count: int = Field(ge=0)
    ocr_text_fingerprint: str | None = None
    application_candidates: tuple[str, ...] = ()
    interface_candidates: tuple[str, ...] = ()
    webpage_candidates: tuple[str, ...] = ()
    service_candidates: tuple[str, ...] = ()
    visible_topic_candidates: tuple[str, ...] = ()
    visible_entity_candidates: tuple[str, ...] = ()
    caption_available: bool = False


class PlaceInsight(DerivedInsight):
    recurrent_places: tuple[dict[str, Any], ...] = ()
    new_places: tuple[dict[str, Any], ...] = ()
    activity_centre_changes: tuple[dict[str, Any], ...] = ()
    travel_periods: tuple[dict[str, Any], ...] = ()
    place_linked_project_episodes: tuple[dict[str, Any], ...] = ()
    media_content_candidates: tuple[MediaContentCandidate, ...] = ()
    candidates: tuple[MediaLocationCandidate, ...] = ()


class ChangeInsight(DerivedInsight):
    change_type: Literal["EMERGING", "DECLINING", "RETURNING", "TEMPORARY_BURST", "REGIME_SHIFT", "ROUTINE_CHANGE"]
    state_key: str
    detected_at: datetime
    baseline_window: tuple[datetime, datetime] | None = None
    current_window: tuple[datetime, datetime] | None = None
    magnitude: float


class ProjectEpisodeView(DerivedInsight):
    start_at: datetime
    end_at: datetime
    topic_ids: tuple[str, ...] = ()
    topic_co_emergence: tuple[str, ...] = ()
    machine_label: str | None = None
    human_label: str | None = None
    peak_investigation_at: datetime | None = None
    progressed_to_creation: bool = False
    progressed_to_implementation: bool = False


class PersonalEraView(DerivedInsight):
    start_at: datetime
    end_at: datetime
    machine_label: str | None = None
    human_label: str | None = None


class ExternalContextEvent(FrozenModel):
    id: UUID
    title: str
    event_type: str
    occurred_at: datetime
    ended_at: datetime | None = None
    topics: tuple[str, ...] = ()
    jurisdiction: str | None = None
    source_uri: str | None = None
    source_artifact_id: UUID | None = None
    ingested_at: datetime


class TemporalCorrelationCandidate(DerivedInsight):
    local_change_id: UUID
    external_event_id: UUID
    local_change: dict[str, Any] = Field(default_factory=dict)
    external_event: dict[str, Any] = Field(default_factory=dict)
    temporal_proximity: float = Field(ge=0, le=1)
    semantic_relevance: float = Field(ge=0, le=1)
    user_exposure_evidence: tuple[InsightEvidenceRef, ...] = ()
    direct_user_statement: bool = False
    preceding_related_activity: bool = False
    behavioural_persistence: float = Field(ge=0)
    competing_explanations_count: int = Field(ge=0)
    status: CorrelationStatus
    causal_claim: Literal[False] = False

    @model_validator(mode="after")
    def relation_guard(self):
        if self.status is CorrelationStatus.EVIDENCE_SUPPORTED_RELATION and not self.user_exposure_evidence:
            raise ValueError("evidence-supported relation requires local exposure evidence")
        if self.status is CorrelationStatus.USER_CONFIRMED and not self.direct_user_statement:
            raise ValueError("user_confirmed requires a direct user statement")
        return self


class PeriodOverview(FrozenModel):
    subject_id: str
    period: InsightPeriod
    active_topic_count: int = Field(ge=0)
    emerging_topic_count: int = Field(ge=0)
    returning_topic_count: int = Field(ge=0)
    project_episode_count: int = Field(ge=0)
    total_event_count: int = Field(ge=0)
    density: tuple[ActivityDensityBin, ...] = ()
    engagement: InsightEngagementProfile | None = None


class InsightTrace(FrozenModel):
    insight_id: UUID
    detector_id: str
    detector_version: str
    analysis_run_id: UUID | None = None
    time_window: tuple[datetime, datetime] | None = None
    calculated_features: dict[str, Any]
    source_counts: dict[str, int]
    activity_events: tuple[dict[str, Any], ...] = ()
    assertions: tuple[dict[str, Any], ...] = ()
    temporal_states: tuple[dict[str, Any], ...] = ()
    temporal_aggregates: tuple[dict[str, Any], ...] = ()
    external_context_events: tuple[dict[str, Any], ...] = ()
    source_artifacts: tuple[dict[str, Any], ...] = ()
    evidence_locators: tuple[dict[str, Any], ...] = ()
    model_explanation: str | None = None


class InsightSnapshot(FrozenModel):
    snapshot_id: UUID
    subject_id: str
    period: InsightPeriod
    comparison: InsightComparisonPeriod | None = None
    analysis_run_ids: tuple[UUID, ...] = ()
    derivation_method: str
    derivation_version: str
    generated_at: datetime
    canonical_source_counts: dict[str, int] = Field(default_factory=dict)
    overview: PeriodOverview
    interests: tuple[ObservedInterestState, ...] = ()
    search: SearchInsight | None = None
    ai_conversations: AIConversationInsight | None = None
    places: PlaceInsight | None = None
    changes: tuple[ChangeInsight, ...] = ()
    project_episodes: tuple[ProjectEpisodeView, ...] = ()
    personal_eras: tuple[PersonalEraView, ...] = ()
    contextual_correlations: tuple[TemporalCorrelationCandidate, ...] = ()
