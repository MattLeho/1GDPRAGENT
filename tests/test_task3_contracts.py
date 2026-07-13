from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from evidence.models import EvidenceLocatorCreate, LocatorType
from ingestion.models import (
    ActivityEvent, ActionClass, ExtractionContext, ExtractionResult, ExtractionUnit,
    FileTypeEvidence, FileTypeTruth, FileTypeTruthValue, ModelAdjudicationBundle,
    PipelineCheckpoint, PipelineStage, CheckpointStatus, QuarantineStatus,
    StructureFingerprint, TemporalPrecision,
)


def test_task3_contracts_preserve_unknown_and_ambiguous_states():
    truth=FileTypeTruth(status=FileTypeTruthValue.AMBIGUOUS,evidence=(FileTypeEvidence(source="extension",value=".bin"),),reason="conflicting evidence")
    assert truth.detected_format is None
    fingerprint=StructureFingerprint(fingerprint_id="a"*64,family="json",provider_id="json_shape",provider_version="1",canonical_shape={"top_level":"array"},sample_count=2)
    assert fingerprint.canonical_shape["top_level"]=="array"


def test_extraction_units_require_payload_and_exact_locator():
    locator={"locator_type":"json_pointer","locator":{"pointer":"/records/0"}}
    with pytest.raises(ValidationError):
        ExtractionUnit(unit_id="u",unit_type="record",ordinal=0,evidence_locator=locator)
    unit=ExtractionUnit(unit_id="u",unit_type="record",ordinal=0,structured_payload={"x":1},evidence_locator=locator)
    result=ExtractionResult(artifact_id=uuid4(),adapter_id="structured",adapter_version="1",family="structured",detected_format="json",units=(unit,),quarantine_status=QuarantineStatus.NONE)
    assert result.units[0].evidence_locator.locator["pointer"]=="/records/0"


def test_checkpoint_idempotency_and_activity_event_contracts():
    run_id=uuid4(); artifact_id=uuid4(); snapshot_id=uuid4(); locator_id=uuid4(); event_id=uuid4()
    checkpoint=PipelineCheckpoint(analysis_run_id=run_id,stage=PipelineStage.PARSING,item_key="artifact",idempotency_key="b"*64,content_hash="c"*64,parser_version="1",status=CheckpointStatus.RUNNING)
    assert checkpoint.stage is PipelineStage.PARSING
    event=ActivityEvent(event_id=event_id,record_signature="d"*64,subject_id="subject",export_snapshot_id=snapshot_id,artifact_id=artifact_id,data_domain="search",event_type="query",action_class=ActionClass.SEARCHED,occurred_at=None,temporal_precision=TemporalPrecision.UNKNOWN,parser_id="p",parser_version="1",source_locator_id=locator_id)
    assert event.temporal_precision is TemporalPrecision.UNKNOWN


def test_model_bundle_is_bounded_and_uses_existing_task_keys():
    bundle=ModelAdjudicationBundle(task_key="schema.interpretation",analysis_run_id=uuid4(),source_artifact_ids=(uuid4(),),purpose="unknown fingerprint",samples=({"shape":"sample"},),maximum_sample_bytes=4096,omitted_record_count=100)
    assert bundle.maximum_sample_bytes==4096
    with pytest.raises(ValidationError):
        ModelAdjudicationBundle(task_key="new.router",analysis_run_id=uuid4(),source_artifact_ids=(),purpose="invalid",samples=(),maximum_sample_bytes=1)


@pytest.mark.parametrize("locator_type,locator",[
    ("json_record",{"record":0,"pointer":"/x"}),
    ("text_line",{"line":1}),
    ("xml_element",{"xpath":"/root/item[1]"}),
    ("pdf_page_block",{"page":1,"block":0}),
    ("spreadsheet_cell",{"sheet":"Sheet1","row":1,"column":1}),
    ("email_mime_part",{"message":0,"part":"1.2"}),
    ("calendar_component",{"component":"VEVENT","uid":"u"}),
    ("subtitle_cue",{"cue":1,"start_ms":0,"end_ms":1000}),
    ("geospatial_feature",{"feature":0}),
    ("database_cell",{"table":"events","row_key":{"id":1},"column":"value"}),
])
def test_task3a_locator_vocabulary_is_canonical(locator_type,locator):
    created=EvidenceLocatorCreate(artifact_id=uuid4(),locator_type=LocatorType(locator_type),locator=locator)
    assert created.locator_type.value==locator_type


def test_extraction_context_is_run_and_snapshot_scoped():
    context=ExtractionContext(artifact_id=uuid4(),analysis_run_id=uuid4(),export_snapshot_id=uuid4(),source_path="data.json")
    assert context.archive_depth==0
