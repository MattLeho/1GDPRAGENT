"""Task 3 local-first ingestion catalogue and run APIs."""

from dataclasses import asdict
from datetime import datetime
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.postgres import get_postgres_client
from ingestion.bulk import BulkIngestionService
from ingestion.registry import FORMAT_SUPPORT_REGISTRY


router=APIRouter(prefix="/bulk-ingestion",tags=["Bulk ingestion"])


class ProcessFileBody(BaseModel):
    file_path: str
    analysis_run_id: UUID | None = None
    export_snapshot_id: UUID | None = None
    request_id: UUID | None = None
    profile_id: UUID | None = None
    received_data_id: UUID | None = None
    source_type: Literal["controller_export","takeout_export","dsar_response","manual_import"] = "manual_import"
    controller_key: str | None = None
    exported_at: datetime | None = None
    declared_mime: str | None = None
    original_path: str | None = None
    requested_tasks: tuple[str, ...] = Field(default=(), max_length=10)


class SpecialistResultBody(BaseModel):
    specialist_request_id: UUID
    execution_record_id: UUID | None = None
    status: Literal["completed","failed","blocked"]
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@router.get("/support")
async def support_catalogue():
    """Return the canonical machine-readable Task 3A support registry."""
    return {
        "registry_version":"task3a-1",
        "formats":[record.model_dump(mode="json") for record in FORMAT_SUPPORT_REGISTRY],
    }


@router.post("/process")
async def process_file(body: ProcessFileBody):
    service=BulkIngestionService()
    try:
        if (body.analysis_run_id is None) != (body.export_snapshot_id is None):
            raise ValueError("analysis_run_id and export_snapshot_id must be supplied together")
        if body.analysis_run_id is None:
            run_id,snapshot_id=await service.prepare_run(
                request_id=body.request_id,profile_id=body.profile_id,
                source_type=body.source_type,controller_key=body.controller_key,
                exported_at=body.exported_at,
                configuration={"entrypoint":"bulk-ingestion/process","received_data_id":str(body.received_data_id) if body.received_data_id else None},
            )
        else:
            run_id,snapshot_id=body.analysis_run_id,body.export_snapshot_id
        result=await service.process_file(
            body.file_path,analysis_run_id=run_id,export_snapshot_id=snapshot_id,
            declared_mime=body.declared_mime,original_path=body.original_path,
            requested_tasks=body.requested_tasks,received_data_id=body.received_data_id,
        )
        return asdict(result)
    except (ValueError,OSError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/enqueue",status_code=202)
async def enqueue_file(body: ProcessFileBody):
    if body.analysis_run_id is not None or body.export_snapshot_id is not None:
        raise HTTPException(status_code=422,detail="enqueue creates its own run and snapshot")
    service=BulkIngestionService()
    try:
        # Validate the read-only source boundary before a task is accepted.
        from ingestion.bulk import resolve_import_path
        resolve_import_path(body.file_path,service.import_roots)
        run_id,snapshot_id=await service.prepare_run(
            request_id=body.request_id,profile_id=body.profile_id,
            source_type=body.source_type,controller_key=body.controller_key,
            exported_at=body.exported_at,
            configuration={"entrypoint":"bulk-ingestion/enqueue","received_data_id":str(body.received_data_id) if body.received_data_id else None},
        )
        from tasks import app as celery_app
        task=celery_app.send_task("intelligence.bulk_ingestion.process_file",args=[{
            **body.model_dump(mode="json"),"analysis_run_id":str(run_id),
            "export_snapshot_id":str(snapshot_id),
        }])
        return {"analysis_run_id":run_id,"export_snapshot_id":snapshot_id,"task_id":task.id,"status":"queued"}
    except (ValueError,OSError) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/runs/{analysis_run_id}")
async def run_progress(analysis_run_id: UUID):
    postgres=get_postgres_client()
    rows=await postgres.execute(
        """SELECT stage,status,count(*) item_count,sum(attempt) attempts,
        COALESCE(sum((progress->>'bytes')::bigint) FILTER(WHERE progress?'bytes'),0) bytes
        FROM pipeline_checkpoints WHERE analysis_run_id=$1 GROUP BY stage,status ORDER BY stage,status""",
        analysis_run_id,
    )
    files=await postgres.execute(
        """SELECT artifact_id,status,support_status,detected_format,quarantine_reason,next_action,warnings
        FROM file_ingestion_records WHERE analysis_run_id=$1 ORDER BY updated_at,artifact_id""",
        analysis_run_id,
    )
    return {"analysis_run_id":analysis_run_id,"stages":[dict(row) for row in rows],"files":[dict(row) for row in files]}


@router.post("/specialist-results")
async def specialist_result(body: SpecialistResultBody):
    postgres=get_postgres_client()
    pool=await postgres._get_pool()
    async with pool.acquire() as connection,connection.transaction():
        request=await connection.fetchrow(
            "SELECT * FROM specialist_task_requests WHERE id=$1 FOR UPDATE",
            body.specialist_request_id,
        )
        if request is None: raise HTTPException(status_code=404,detail="specialist request not found")
        if request["status"]=="completed": return {"success":True,"already_recorded":True}
        if body.execution_record_id is not None:
            audit=await connection.fetchrow(
                "SELECT task_key,source_artifact_ids FROM execution_records WHERE id=$1",
                body.execution_record_id,
            )
            if audit is None or audit["task_key"]!=request["task_key"] or request["artifact_id"] not in audit["source_artifact_ids"]:
                raise HTTPException(status_code=409,detail="execution record does not match specialist request")
        await connection.execute(
            """UPDATE specialist_task_requests SET status=$2,execution_record_id=$3,
            output_manifest=$4::jsonb,error=$5::jsonb,completed_at=NOW() WHERE id=$1""",
            body.specialist_request_id,body.status,body.execution_record_id,
            json.dumps(body.output,default=str) if body.output is not None else None,
            json.dumps(body.error,default=str) if body.error is not None else None,
        )
    if body.status=="completed" and body.output:
        await _persist_specialist_units(postgres,dict(request),body.output)
    return {"success":True,"status":body.status}


async def _persist_specialist_units(postgres,request:dict[str,Any],output:dict[str,Any])->None:
    from evidence.ledger import EvidenceLedger
    ledger=EvidenceLedger(postgres)
    manifest=request["input_manifest"]
    if isinstance(manifest,str):manifest=json.loads(manifest)
    text=str(output.get("text") or "")
    units=[]
    if request["task_key"] in {"speech.transcription","speech.translation","speech.diarisation"}:
        for index,segment in enumerate(output.get("segments") or []):
            start=int(float(segment.get("start",0))*1000);end=int(float(segment.get("end",0))*1000)
            if end<=start:continue
            units.append((f"transcript-{index}","transcript_segment",index,"media_time_range",{"start_ms":start,"end_ms":end},segment.get("text"),segment))
    elif request["task_key"] in {"image.ocr","document.ocr"}:
        for index,word in enumerate(output.get("words") or []):
            if not word.get("text") or float(word.get("width",0))<=0 or float(word.get("height",0))<=0:continue
            units.append((f"ocr-{index}","ocr_word",index,"image_region",{
                "x":float(word.get("left",0)),"y":float(word.get("top",0)),
                "width":float(word["width"]),"height":float(word["height"]),
            },word.get("text"),word))
    for unit_key,unit_type,ordinal,locator_type,locator,unit_text,metadata in units:
        locator_id=await ledger.create_unverified_locator(request["artifact_id"],locator_type,locator,reason="specialist-derived locator pending source-region verification")
        await postgres.execute(
            """INSERT INTO extraction_units
            (analysis_run_id,artifact_id,unit_key,unit_type,ordinal,text_value,metadata,evidence_locator_id,adapter_id,adapter_version)
            VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,'task2_specialist_router',$9)
            ON CONFLICT(analysis_run_id,artifact_id,adapter_id,adapter_version,unit_key) DO NOTHING""",
            request["analysis_run_id"],request["artifact_id"],unit_key,unit_type,ordinal,unit_text,
            json.dumps({**metadata,"engine":output.get("engine"),"model":output.get("model"),
                        "derivation_version":output.get("derivation_version"),"confidence":metadata.get("confidence")},default=str),
            locator_id,str(output.get("derivation_version") or output.get("model") or "1"),
        )
    received_id=manifest.get("received_data_id")
    if received_id and text:
        column="transcript" if request["task_key"].startswith("speech.") else "extracted_text"
        await postgres.execute(
            f"""UPDATE received_data SET {column}=$2,markdown_content=$2,status='completed',
            processing_stage='completed',processing_progress=100,processing_completed_at=NOW(),
            derived_content_basis='task2_specialist_router',provenance_status='specialist_candidate'
            WHERE id=$1""",UUID(received_id),text,
        )
