from __future__ import annotations

from datetime import datetime
from enum import Enum
import json
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FileTypeTruthValue(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class SupportStatus(str, Enum):
    SUPPORTED_DETERMINISTIC = "SUPPORTED_DETERMINISTIC"
    SUPPORTED_WITH_OPTIONAL_SPECIALIST = "SUPPORTED_WITH_OPTIONAL_SPECIALIST"
    METADATA_ONLY = "METADATA_ONLY"
    QUARANTINED = "QUARANTINED"
    UNSUPPORTED = "UNSUPPORTED"


class QuarantineStatus(str, Enum):
    NONE = "none"
    PASSWORD_REQUIRED = "password_required"
    ENCRYPTED = "encrypted"
    CORRUPT = "corrupt"
    POLICY_LIMIT = "policy_limit"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


class ReviewStatus(str, Enum):
    UNKNOWN = "unknown"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class PipelineStage(str, Enum):
    INVENTORY = "inventory"
    HASHING = "hashing"
    FILE_TYPING = "file_typing"
    FAMILY_EXTRACTION = "family_extraction"
    FINGERPRINTING = "fingerprinting"
    PARSING = "parsing"
    NORMALISATION = "normalisation"
    FEATURE_EXTRACTION = "feature_extraction"
    TEMPORAL_AGGREGATION = "temporal_aggregation"
    ASSERTION_GENERATION = "assertion_generation"
    GRAPH_PROJECTION = "graph_projection"


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    SKIPPED = "skipped"


class TemporalPrecision(str, Enum):
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


class ActionClass(str, Enum):
    CONSUMED = "CONSUMED"
    SEARCHED = "SEARCHED"
    CREATED = "CREATED"
    EDITED = "EDITED"
    PUBLISHED = "PUBLISHED"
    CODED = "CODED"
    COMMUNICATED = "COMMUNICATED"
    PURCHASED = "PURCHASED"
    VISITED = "VISITED"
    AUTHENTICATED = "AUTHENTICATED"
    OTHER = "OTHER"


class FeatureCandidateStatus(str, Enum):
    DETERMINISTIC = "deterministic"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"
    ADJUDICATION_REQUIRED = "adjudication_required"


class PrivacyDataClass(str, Enum):
    DIRECT_IDENTIFIER = "DIRECT_IDENTIFIER"
    QUASI_IDENTIFIER = "QUASI_IDENTIFIER"
    CONTACT = "CONTACT"
    LOCATION = "LOCATION"
    COMMUNICATION = "COMMUNICATION"
    SOCIAL_INTERACTION = "SOCIAL_INTERACTION"
    BEHAVIOURAL_EVENT = "BEHAVIOURAL_EVENT"
    SEARCH_HISTORY = "SEARCH_HISTORY"
    CONTENT_CONSUMPTION = "CONTENT_CONSUMPTION"
    PURCHASE = "PURCHASE"
    PAYMENT = "PAYMENT"
    DEVICE = "DEVICE"
    AUTHENTICATION = "AUTHENTICATION"
    SECURITY_EVENT = "SECURITY_EVENT"
    ADVERTISEMENT = "ADVERTISEMENT"
    INFERRED_ATTRIBUTE = "INFERRED_ATTRIBUTE"
    DECLARED_ATTRIBUTE = "DECLARED_ATTRIBUTE"
    BIOMETRIC_CANDIDATE = "BIOMETRIC_CANDIDATE"
    MEDIA = "MEDIA"
    DOCUMENT = "DOCUMENT"
    UNKNOWN = "UNKNOWN"


class HistoryType(str, Enum):
    PERSONAL_BEHAVIOURAL = "personal_behavioural"
    CONTROLLER_PROFILE = "controller_profile"
    SYSTEM_UNDERSTANDING = "system_understanding"


class InventoryEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    size: int = Field(ge=0)
    modified_at: datetime | None = None
    is_symlink: bool = False
    archive_depth: int = Field(default=0, ge=0)
    parent_artifact_id: UUID | None = None
    archive_member_chain: tuple[str, ...] = ()


class ArchiveMemberObservation(FrozenModel):
    outer_artifact_id: UUID
    member_path: str = Field(min_length=1)
    member_ordinal: int = Field(ge=0)
    compressed_size: int | None = Field(default=None, ge=0)
    uncompressed_size: int | None = Field(default=None, ge=0)
    expansion_ratio: float | None = Field(default=None, ge=0)
    nesting_depth: int = Field(ge=1)
    duplicate_path: bool = False
    traversal_attempt: bool = False
    absolute_path: bool = False
    symlink: bool = False


class FileTypeEvidence(FrozenModel):
    source: Literal["extension", "declared_mime", "signature", "parser_probe"]
    value: str | None = None
    candidate_format: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    error: str | None = None


class FileTypeTruth(FrozenModel):
    status: FileTypeTruthValue
    detected_format: str | None = None
    detected_mime: str | None = None
    evidence: tuple[FileTypeEvidence, ...]
    reason: str


class StructureFingerprint(FrozenModel):
    fingerprint_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    family: str
    provider_id: str
    provider_version: str
    canonical_shape: dict[str, Any]
    sample_count: int = Field(ge=0)


class EvidenceLocatorValue(FrozenModel):
    locator_type: str = Field(min_length=1)
    locator: dict[str, Any]
    @model_validator(mode="after")
    def canonical_shape(self):
        from evidence.models import validate_locator_shape
        validate_locator_shape(self.locator_type,self.locator)
        return self


class ExtractionUnit(FrozenModel):
    unit_id: str = Field(min_length=1)
    unit_type: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    text: str | None = None
    value: Any | None = None
    structured_payload: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_locator: EvidenceLocatorValue
    parent_unit_id: str | None = None

    @model_validator(mode="after")
    def has_payload(self):
        if self.text is None and self.value is None and self.structured_payload is None:
            raise ValueError("an extraction unit requires text, value, or structured_payload")
        return self


class EmbeddedMember(FrozenModel):
    member_path: str
    ordinal: int = Field(ge=0)
    declared_size: int | None = Field(default=None, ge=0)
    media_type: str | None = None
    content: bytes | None = Field(default=None, repr=False, exclude=True)
    evidence_locator: EvidenceLocatorValue | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def content_matches_declared_size(self):
        if self.content is not None and self.declared_size is not None and len(self.content) != self.declared_size:
            raise ValueError("embedded member content does not match declared_size")
        return self


class ExtractionResult(FrozenModel):
    artifact_id: UUID
    adapter_id: str
    adapter_version: str
    family: str
    detected_format: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    units: tuple[ExtractionUnit, ...] = ()
    embedded_members: tuple[EmbeddedMember, ...] = ()
    warnings: tuple[str, ...] = ()
    quarantine_status: QuarantineStatus = QuarantineStatus.NONE


class ProbeResult(FrozenModel):
    accepted: bool
    confidence: float = Field(ge=0, le=1)
    detected_format: str | None = None
    reason: str


class ExtractionContext(FrozenModel):
    artifact_id: UUID
    analysis_run_id: UUID
    export_snapshot_id: UUID
    source_path: str
    archive_depth: int = Field(default=0, ge=0)
    configuration: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class FileFamilyAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    family: str
    supported_mime_types: frozenset[str]
    supported_extensions: frozenset[str]
    supports_streaming: bool
    supports_nested_members: bool
    locator_types: frozenset[str]
    capability_flags: frozenset[str]

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult: ...
    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult: ...


class FormatSupportRecord(FrozenModel):
    format_key: str
    family: str
    probe_priority: int = Field(ge=0)
    adapter_id: str | None
    adapter_version: str | None
    status: SupportStatus
    supported_extensions: tuple[str, ...] = ()
    supported_mime_types: tuple[str, ...] = ()
    magic_signatures: tuple[str, ...] = ()
    task_routes: tuple[str, ...] = ()
    capability_flags: tuple[str, ...] = ()
    locator_types: tuple[str, ...] = ()
    streaming: bool = False
    maximum_tested_fixture_size: int | None = Field(default=None, ge=0)
    system_dependencies: tuple[str, ...] = ()
    security_notes: tuple[str, ...] = ()
    known_unsupported_features: tuple[str, ...] = ()
    fixture_ids: tuple[str, ...] = ()


class SchemaRegistryEntry(FrozenModel):
    fingerprint_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_service: str | None = None
    data_domain: str
    file_family: str
    parser_id: str
    parser_version: str
    normalised_event_type: str
    review_status: ReviewStatus
    approved_at: datetime | None = None
    approved_by: str | None = None


class DeclarativeParserSpec(FrozenModel):
    parser_id: str
    parser_version: str
    file_family: str
    event_type: str
    data_domain: str
    timestamp_selector: str | None = None
    temporal_precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    subject_selector: str | None = None
    object_selectors: dict[str, str] = Field(default_factory=dict)
    identifier_selectors: dict[str, str] = Field(default_factory=dict)
    location_selectors: dict[str, str] = Field(default_factory=dict)
    relationship_fields: dict[str, str] = Field(default_factory=dict)
    epistemic_hints: dict[str, Literal["declared", "observed", "inferred"]] = Field(default_factory=dict)
    action_class: ActionClass = ActionClass.OTHER
    service: str | None = None
    product: str | None = None
    object_type: str | None = None


class ParserExecutionResult(FrozenModel):
    parser_id: str
    parser_version: str
    artifact_id: UUID
    records_seen: int = Field(ge=0)
    events_emitted: int = Field(ge=0)
    rejected_records: int = Field(ge=0)
    events: tuple["ActivityEvent", ...] = ()
    warnings: tuple[str, ...] = ()


class ActivityEvent(FrozenModel):
    event_id: UUID
    record_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    subject_id: str
    export_snapshot_id: UUID
    artifact_id: UUID
    service: str | None = None
    product: str | None = None
    data_domain: str
    event_type: str
    action_class: ActionClass = ActionClass.OTHER
    occurred_at: datetime | None = None
    occurred_at_original: Any | None = None
    temporal_precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    timezone: str | None = None
    timezone_evidence: str | None = None
    timezone_assumption: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    object_value: Any | None = None
    identifiers: dict[str, Any] = Field(default_factory=dict)
    locations: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] = Field(default_factory=dict)
    epistemic_hints: dict[str, Literal["declared", "observed", "inferred"]] = Field(default_factory=dict)
    parser_id: str
    parser_version: str
    source_locator_id: UUID
    field_locator_ids: dict[str, UUID] = Field(default_factory=dict)


class ActivityEventObservation(FrozenModel):
    event_id: UUID
    export_snapshot_id: UUID
    artifact_id: UUID
    source_locator_id: UUID
    observed_at: datetime


class EventPartitionRecord(FrozenModel):
    partition_id: UUID
    analysis_run_id: UUID
    path: str
    file_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str
    row_count: int = Field(ge=0)
    min_occurred_at: datetime | None = None
    max_occurred_at: datetime | None = None
    byte_size: int = Field(ge=0)


class PipelineCheckpoint(FrozenModel):
    analysis_run_id: UUID
    stage: PipelineStage
    item_key: str
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parser_version: str | None = None
    status: CheckpointStatus
    attempt: int = Field(default=1, ge=1)
    progress: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


class TemporalState(FrozenModel):
    subject_id: str
    history_type: HistoryType
    state_type: str
    state_key: str
    occurred_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    controller_observed_from: datetime | None = None
    controller_observed_to: datetime | None = None
    exported_at: datetime | None = None
    ingested_at: datetime | None = None
    system_asserted_at: datetime
    superseded_at: datetime | None = None
    dimensions: dict[str, float]
    evidence_event_ids: tuple[UUID, ...] = ()
    detector_id: str
    detector_version: str


class TemporalAggregate(FrozenModel):
    subject_id: str
    history_type: HistoryType
    aggregate_type: str
    aggregate_key: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    values: dict[str, float | int | str | None]
    source_event_count: int = Field(ge=0)
    detector_id: str
    detector_version: str


class ModelAdjudicationBundle(FrozenModel):
    task_key: Literal["schema.interpretation", "semantic.adjudication", "semantic.topic_labelling"]
    analysis_run_id: UUID
    source_artifact_ids: tuple[UUID, ...] = Field(max_length=1024)
    purpose: str = Field(min_length=1, max_length=2048)
    samples: tuple[dict[str, Any], ...] = Field(max_length=256)
    maximum_sample_bytes: int = Field(gt=0)
    omitted_record_count: int = Field(default=0, ge=0)
    fingerprint_id: str | None = None

    @model_validator(mode="after")
    def bounded_samples(self):
        encoded = json.dumps(self.samples, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
        if len(encoded) > self.maximum_sample_bytes:
            raise ValueError("samples exceed maximum_sample_bytes")
        return self


class FeatureCandidate(FrozenModel):
    feature_type: str = Field(min_length=1)
    detector_id: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    source_event_ids: tuple[UUID, ...] = ()
    source_artifact_ids: tuple[UUID, ...] = ()
    calculated_values: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    rule_result: bool | None = None
    candidate_status: FeatureCandidateStatus

    @model_validator(mode="after")
    def grounded_source(self):
        if not self.source_event_ids and not self.source_artifact_ids:
            raise ValueError("feature candidates require source event or artefact references")
        if self.confidence is None and self.rule_result is None:
            raise ValueError("feature candidates require confidence or a rule result")
        return self


class OpaqueIdentifierCandidate(FrozenModel):
    token_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    occurrence_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    service_count: int = Field(ge=0)
    domain_count: int = Field(ge=0)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    entropy_bits_per_character: float = Field(ge=0)
    recurrence_ratio: float = Field(ge=0, le=1)
    cross_schema_count: int = Field(ge=0)
    cross_domain_count: int = Field(ge=0)
    assigned_meaning: None = None
