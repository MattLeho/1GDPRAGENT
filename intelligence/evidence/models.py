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
    JSON_POINTER="json_pointer"; JSON_RECORD="json_record"; CSV_ROW="csv_row"; CSV_CELL="csv_cell"
    TEXT_SPAN="text_span"; TEXT_LINE="text_line"; TEXT_BYTE_SPAN="text_byte_span"
    XML_ELEMENT="xml_element"; HTML_DOM_SPAN="html_dom_span"
    PDF_PAGE_BLOCK="pdf_page_block"; PDF_REGION="pdf_region"
    OFFICE_PARAGRAPH="office_paragraph"; OFFICE_TABLE_CELL="office_table_cell"
    SPREADSHEET_CELL="spreadsheet_cell"; SLIDE_SHAPE="slide_shape"; SLIDE_NOTES="slide_notes"
    EMAIL_HEADER="email_header"; EMAIL_MIME_PART="email_mime_part"; EMAIL_ATTACHMENT="email_attachment"
    CALENDAR_COMPONENT="calendar_component"; VCARD_PROPERTY="vcard_property"
    MEDIA_TIME_RANGE="media_time_range"; IMAGE_REGION="image_region"; VIDEO_FRAME="video_frame"; SUBTITLE_CUE="subtitle_cue"
    GEOSPATIAL_FEATURE="geospatial_feature"; DATABASE_TABLE_ROW="database_table_row"; DATABASE_CELL="database_cell"
    ARCHIVE_MEMBER="archive_member"


class JsonPointerLocator(FrozenModel):
    pointer: str = Field(pattern=r"^(|/.*)$")
class JsonRecordLocator(FrozenModel):
    record: int = Field(ge=0)
    pointer: str = Field(default="", pattern=r"^(|/.*)$")
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
class TextLineLocator(FrozenModel):
    line: int = Field(ge=1)
    column_start: int | None = Field(default=None, ge=0)
    column_end: int | None = Field(default=None, gt=0)
class TextByteSpanLocator(FrozenModel):
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    @model_validator(mode="after")
    def ordered(self):
        if self.byte_end <= self.byte_start: raise ValueError("byte_end must exceed byte_start")
        return self
class XmlElementLocator(FrozenModel):
    xpath: str = Field(min_length=1)
    attribute: str | None = None
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
    outer_artifact_id: UUID | None = None
    nested_member_chain: tuple[str, ...] = ()
    member_ordinal: int | None = Field(default=None, ge=0)
class PdfPageBlockLocator(FrozenModel):
    page: int = Field(ge=1); block: int = Field(ge=0)
class PdfRegionLocator(FrozenModel):
    page: int = Field(ge=1); x: float = Field(ge=0); y: float = Field(ge=0); width: float = Field(gt=0); height: float = Field(gt=0)
class OfficeParagraphLocator(FrozenModel):
    paragraph: int = Field(ge=0); run: int | None = Field(default=None, ge=0)
class OfficeTableCellLocator(FrozenModel):
    table: int = Field(ge=0); row: int = Field(ge=0); column: int = Field(ge=0)
class SpreadsheetCellLocator(FrozenModel):
    sheet: str = Field(min_length=1); row: int = Field(ge=1); column: int = Field(ge=1); address: str | None = None
class SlideShapeLocator(FrozenModel):
    slide: int = Field(ge=1); shape: int = Field(ge=0)
class SlideNotesLocator(FrozenModel):
    slide: int = Field(ge=1); note: int = Field(default=0, ge=0)
class EmailHeaderLocator(FrozenModel):
    message: int = Field(ge=0); header: str = Field(min_length=1); occurrence: int = Field(default=0, ge=0)
class EmailMimePartLocator(FrozenModel):
    message: int = Field(ge=0); part: str = Field(min_length=1)
class EmailAttachmentLocator(FrozenModel):
    message: int = Field(ge=0); part: str = Field(min_length=1); filename: str | None = None
class CalendarComponentLocator(FrozenModel):
    component: str = Field(min_length=1); uid: str | None = None; occurrence: int = Field(default=0, ge=0); property: str | None = None
class VcardPropertyLocator(FrozenModel):
    card: int = Field(ge=0); property: str = Field(min_length=1); occurrence: int = Field(default=0, ge=0)
class VideoFrameLocator(FrozenModel):
    timestamp_ms: int = Field(ge=0); frame: int | None = Field(default=None, ge=0)
class SubtitleCueLocator(FrozenModel):
    cue: int = Field(ge=1); start_ms: int = Field(ge=0); end_ms: int = Field(gt=0)
class GeospatialFeatureLocator(FrozenModel):
    feature: str | int; coordinate: int | None = Field(default=None, ge=0); segment: int | None = Field(default=None, ge=0)
class DatabaseTableRowLocator(FrozenModel):
    table: str = Field(min_length=1); row_key: dict[str,Any]
class DatabaseCellLocator(FrozenModel):
    table: str = Field(min_length=1); row_key: dict[str,Any]; column: str = Field(min_length=1)

Locator = Union[JsonPointerLocator,JsonRecordLocator,CsvRowLocator,CsvCellLocator,TextSpanLocator,TextLineLocator,
    TextByteSpanLocator,XmlElementLocator,HtmlDomSpanLocator,PdfPageBlockLocator,PdfRegionLocator,
    OfficeParagraphLocator,OfficeTableCellLocator,SpreadsheetCellLocator,SlideShapeLocator,SlideNotesLocator,
    EmailHeaderLocator,EmailMimePartLocator,EmailAttachmentLocator,CalendarComponentLocator,VcardPropertyLocator,
    MediaTimeRangeLocator,ImageRegionLocator,VideoFrameLocator,SubtitleCueLocator,GeospatialFeatureLocator,
    DatabaseTableRowLocator,DatabaseCellLocator,ArchiveMemberLocator]

LOCATOR_MODELS={
    LocatorType.JSON_POINTER:JsonPointerLocator,LocatorType.JSON_RECORD:JsonRecordLocator,
    LocatorType.CSV_ROW:CsvRowLocator,LocatorType.CSV_CELL:CsvCellLocator,
    LocatorType.TEXT_SPAN:TextSpanLocator,LocatorType.TEXT_LINE:TextLineLocator,LocatorType.TEXT_BYTE_SPAN:TextByteSpanLocator,
    LocatorType.XML_ELEMENT:XmlElementLocator,LocatorType.HTML_DOM_SPAN:HtmlDomSpanLocator,
    LocatorType.PDF_PAGE_BLOCK:PdfPageBlockLocator,LocatorType.PDF_REGION:PdfRegionLocator,
    LocatorType.OFFICE_PARAGRAPH:OfficeParagraphLocator,LocatorType.OFFICE_TABLE_CELL:OfficeTableCellLocator,
    LocatorType.SPREADSHEET_CELL:SpreadsheetCellLocator,LocatorType.SLIDE_SHAPE:SlideShapeLocator,LocatorType.SLIDE_NOTES:SlideNotesLocator,
    LocatorType.EMAIL_HEADER:EmailHeaderLocator,LocatorType.EMAIL_MIME_PART:EmailMimePartLocator,LocatorType.EMAIL_ATTACHMENT:EmailAttachmentLocator,
    LocatorType.CALENDAR_COMPONENT:CalendarComponentLocator,LocatorType.VCARD_PROPERTY:VcardPropertyLocator,
    LocatorType.MEDIA_TIME_RANGE:MediaTimeRangeLocator,LocatorType.IMAGE_REGION:ImageRegionLocator,LocatorType.VIDEO_FRAME:VideoFrameLocator,
    LocatorType.SUBTITLE_CUE:SubtitleCueLocator,LocatorType.GEOSPATIAL_FEATURE:GeospatialFeatureLocator,
    LocatorType.DATABASE_TABLE_ROW:DatabaseTableRowLocator,LocatorType.DATABASE_CELL:DatabaseCellLocator,
    LocatorType.ARCHIVE_MEMBER:ArchiveMemberLocator,
}

def validate_locator_shape(locator_type: LocatorType | str, locator: dict[str,Any]) -> dict[str,Any]:
    kind=LocatorType(locator_type)
    return LOCATOR_MODELS[kind].model_validate(locator).model_dump(mode="json",exclude_none=True)


class EvidenceLocatorCreate(FrozenModel):
    artifact_id: UUID
    locator_type: LocatorType
    locator: dict[str, Any]
    expected_text: str | None = None
    expected_raw_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    @model_validator(mode="after")
    def locator_shape(self):
        validate_locator_shape(self.locator_type,self.locator)
        return self


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
