from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AnalysisRunStatus(str, Enum):
    PENDING="pending"; RUNNING="running"; COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"
class DataClass(str, Enum):
    DECLARED="declared"; OBSERVED="observed"; DERIVED="derived"; INFERRED="inferred"
class AssertionStatus(str, Enum):
    CANDIDATE="candidate"; ACCEPTED="accepted"; REJECTED="rejected"; SUPERSEDED="superseded"
class EpistemicBasis(str, Enum):
    SOURCE_EXPLICIT="source_explicit"; CONTROLLER_ASSIGNED="controller_assigned"; DETERMINISTIC_DERIVATION="deterministic_derivation"; MODEL_HYPOTHESIS="model_hypothesis"; HUMAN_CONFIRMED="human_confirmed"
class LocatorType(str, Enum):
    JSON_POINTER="json_pointer"; CSV_ROW="csv_row"; CSV_CELL="csv_cell"; TEXT_SPAN="text_span"; HTML_DOM_SPAN="html_dom_span"; MEDIA_TIME_RANGE="media_time_range"; IMAGE_REGION="image_region"; ARCHIVE_MEMBER="archive_member"


class JsonPointerLocator(FrozenModel):
    pointer: str = Field(pattern=r"^(|/.*)$")
class CsvRowLocator(FrozenModel):
    row: int = Field(ge=1)
class CsvCellLocator(FrozenModel):
    row: int = Field(ge=1)
    column: str | int
class TextSpanLocator(FrozenModel):
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    @model_validator(mode="after")
    def ordered(self):
        if self.byte_end <= self.byte_start: raise ValueError("byte_end must exceed byte_start")
        return self
class HtmlDomSpanLocator(FrozenModel):
    selector: str = Field(min_length=1)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, gt=0)
class MediaTimeRangeLocator(FrozenModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    @model_validator(mode="after")
    def ordered(self):
        if self.end_ms <= self.start_ms: raise ValueError("end_ms must exceed start_ms")
        return self
class ImageRegionLocator(FrozenModel):
    x: float = Field(ge=0); y: float = Field(ge=0); width: float = Field(gt=0); height: float = Field(gt=0)
class ArchiveMemberLocator(FrozenModel):
    member_path: str = Field(min_length=1)

Locator = Union[JsonPointerLocator,CsvRowLocator,CsvCellLocator,TextSpanLocator,HtmlDomSpanLocator,MediaTimeRangeLocator,ImageRegionLocator,ArchiveMemberLocator]


class EvidenceLocatorCreate(FrozenModel):
    artifact_id: UUID
    locator_type: LocatorType
    locator: dict[str, Any]
    expected_text: str | None = None
    expected_raw_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AnalysisRun(FrozenModel):
    id: UUID; run_type: str; profile_id: UUID | None; request_id: UUID | None; status: AnalysisRunStatus
    pipeline_version: str; configuration: dict[str,Any]; started_at: datetime | None; completed_at: datetime | None
    error: str | None; created_at: datetime


class ExportSnapshot(FrozenModel):
    id: UUID; profile_id: UUID | None; request_id: UUID | None; controller_key: str | None
    source_type: Literal["controller_export","takeout_export","dsar_response","manual_import"]
    exported_at: datetime | None; ingested_at: datetime; analysis_run_id: UUID; metadata: dict[str,Any]


class ContentBlob(FrozenModel):
    id: UUID; sha256: str = Field(pattern=r"^[0-9a-f]{64}$"); byte_size: int = Field(ge=0)
    storage_uri: str; first_ingested_at: datetime


class SourceArtifact(FrozenModel):
    id: UUID; export_snapshot_id: UUID; parent_artifact_id: UUID | None; content_blob_id: UUID
    original_path: str; archive_member_path: str | None; file_name: str; declared_mime: str | None
    detected_mime: str | None; extension: str | None
    file_type_status: Literal["declared","detected","matched","mismatch","unknown"]
    canonical_hash: str | None; structure_fingerprint_id: UUID | None; source_organisation: str | None
    source_product: str | None; source_service: str | None; created_at: datetime


class EvidenceLocatorRecord(FrozenModel):
    id: UUID; artifact_id: UUID; locator_type: LocatorType; locator: dict[str,Any]; raw_hash: str
    verified: bool; verification_method: Literal["mechanical_resolution","exact_quote_match","structured_value_match","human_verified"]
    verification_error: str | None; created_at: datetime


class AssertionCreate(FrozenModel):
    subject_type: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_type: Literal["node_ref","literal","json","unknown"]
    object_ref: str | None = None
    object_value: Any | None = None
    assertion_type: Literal["fact","relationship","classification","hypothesis"]
    data_class: DataClass
    status: AssertionStatus = AssertionStatus.CANDIDATE
    epistemic_basis: EpistemicBasis
    confidence: float | None = Field(default=None, ge=0, le=1)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    temporal_precision: Literal["exact","day","month","year","range","unknown"] = "unknown"
    controller_observed_from: datetime | None = None
    controller_observed_to: datetime | None = None
    exported_at: datetime | None = None
    ingested_at: datetime
    derivation_method: str = Field(min_length=1)
    derivation_version: str = Field(min_length=1)
    analysis_run_id: UUID
    evidence_locator_ids: tuple[UUID, ...] = ()
    source_assertion_ids: tuple[UUID, ...] = ()
    @model_validator(mode="after")
    def exactly_one_object(self):
        if (self.object_ref is None) == (self.object_value is None):
            raise ValueError("exactly one of object_ref and object_value is required")
        return self


class AssertionRecord(AssertionCreate):
    id: UUID
    system_asserted_at: datetime
    superseded_at: datetime | None = None
    supersedes_assertion_id: UUID | None = None
