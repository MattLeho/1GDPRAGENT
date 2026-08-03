from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from evidence.ledger import EvidenceLedger
from request_domain import RequestRepository
from evidence.models import AssertionCreate, AssertionStatus, DataClass, EpistemicBasis
from graph.ontology import canonical_entity_key
from graph.projection import GraphProjectionService
from api.security import require_profile_id


router=APIRouter(prefix="/evidence",tags=["Evidence"])


class ManualNodeRequest(BaseModel):
    type: str
    label: str
    properties: dict[str,Any]=Field(default_factory=dict)
    subject_ref: str="local-subject"


class ProjectRequest(BaseModel):
    assertion_id: UUID

class ManualRetireRequest(BaseModel):
    node_id: UUID
    subject_ref: str="local-subject"

class ManualMergeRequest(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    subject_ref: str="local-subject"

class EntityKeyRequest(BaseModel):
    entity_type: str
    value: str
    controller: str | None=None
    service: str | None=None
    identifier_type: str | None=None

class OnsitBulkRequest(BaseModel):
    action: str
    finding_ids: list[UUID]=Field(min_length=1,max_length=100)
    payload: dict[str,Any]=Field(default_factory=dict)

class SourceArtifactRequest(BaseModel):
    file_path: str
    request_id: UUID | None=None
    declared_mime: str | None=None
    source_organisation: str | None=None


@router.post("/manual-node")
async def manual_node(request: Request, body: ManualNodeRequest):
    profile_id=require_profile_id(request)
    try:
        ledger=EvidenceLedger(); run_id=await ledger.create_analysis_run("manual_graph_edit","task1-manual-v1",profile_id=profile_id,configuration={"ui":"graph"})
        scope=str(body.properties.get("controller") or body.properties.get("service") or "manual")
        node_type={"Company":"Organisation","Organization":"Organisation","User":"Subject","Persona":"Subject","Entity":"DataPoint"}.get(body.type,body.type)
        key=canonical_entity_key("organisation" if node_type=="Organisation" else "identifier",body.label,controller=scope,identifier_type=node_type)
        assertion=AssertionCreate(subject_type="Subject",subject_ref=body.subject_ref,predicate="HUMAN_ASSERTED",object_type="node_ref",object_ref=f"{node_type}:{key}",assertion_type="relationship",data_class=DataClass.DECLARED,status=AssertionStatus.ACCEPTED,epistemic_basis=EpistemicBasis.HUMAN_CONFIRMED,confidence=1.0,ingested_at=datetime.now(timezone.utc),derivation_method="manual_graph_edit",derivation_version="task1-manual-v1",analysis_run_id=run_id)
        assertion_id=await ledger.create_assertion(assertion); projected=await GraphProjectionService().project_assertion(assertion_id,profile_id)
        return {"success":True,"assertion_id":assertion_id,"node_id":projected["object_id"]}
    except (ValueError,KeyError) as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/project")
async def project(request: Request, body: ProjectRequest):
    profile_id=require_profile_id(request)
    try: return await GraphProjectionService().project_assertion(body.assertion_id,profile_id)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc


async def _human_mutation_assertion(profile_id: UUID, subject_ref: str, predicate: str, object_ref: str) -> UUID:
    ledger=EvidenceLedger(); run_id=await ledger.create_analysis_run("manual_graph_edit","task1-manual-v1",profile_id=profile_id,configuration={"ui":"graph"})
    return await ledger.create_assertion(AssertionCreate(subject_type="Subject",subject_ref=subject_ref,predicate=predicate,object_type="node_ref",object_ref=object_ref,assertion_type="relationship",data_class=DataClass.DECLARED,status=AssertionStatus.ACCEPTED,epistemic_basis=EpistemicBasis.HUMAN_CONFIRMED,confidence=1.0,ingested_at=datetime.now(timezone.utc),derivation_method="manual_graph_edit",derivation_version="task1-manual-v1",analysis_run_id=run_id))


@router.post("/manual-retire")
async def manual_retire(request: Request, body: ManualRetireRequest):
    profile_id=require_profile_id(request)
    try:
        assertion_id=await _human_mutation_assertion(profile_id,body.subject_ref,"SUPERSEDES",f"Claim:retire:{body.node_id}")
        await GraphProjectionService().retire_node(assertion_id,body.node_id,profile_id)
        return {"success":True,"assertion_id":assertion_id,"node_id":body.node_id}
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post("/manual-merge")
async def manual_merge(request: Request, body: ManualMergeRequest):
    profile_id=require_profile_id(request)
    try:
        assertion_id=await _human_mutation_assertion(profile_id,body.subject_ref,"RELATES_TO",f"Claim:merge:{body.source_node_id}:{body.target_node_id}")
        await GraphProjectionService().merge_nodes(assertion_id,body.source_node_id,body.target_node_id,profile_id)
        return {"success":True,"assertion_id":assertion_id,"node_id":body.target_node_id}
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post("/backfill-graph")
async def backfill_graph(request: Request):
    require_profile_id(request)
    raise HTTPException(status_code=403,detail="global graph maintenance is unavailable through profile authority")


@router.post("/entity-key")
async def entity_key(body: EntityKeyRequest):
    try:
        key=canonical_entity_key(body.entity_type,body.value,controller=body.controller,service=body.service,identifier_type=body.identifier_type)
        return {"canonical_key":key}
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/onsit-bulk")
async def onsit_bulk(request: Request, body: OnsitBulkRequest):
    profile_id=require_profile_id(request)
    try:
        assertion_id=await _human_mutation_assertion(profile_id,"local-subject","HUMAN_ASSERTED",f"Claim:onsit-bulk:{body.action}:{','.join(map(str,body.finding_ids))}")
        affected=await GraphProjectionService().mutate_onsit(assertion_id,body.action,body.finding_ids,body.payload,profile_id)
        return {"success":True,"action":body.action,"affected":affected,"requested":len(body.finding_ids),"assertion_id":assertion_id}
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc

@router.post("/source-artifact")
async def source_artifact(request: Request, body: SourceArtifactRequest):
    """Register a file occurrence through the Task 1 evidence ledger before analysis."""
    profile_id=require_profile_id(request)
    path=Path(body.file_path).resolve()
    if not path.is_file(): raise HTTPException(status_code=404,detail="Source file does not exist")
    ledger=EvidenceLedger()
    if body.request_id is not None:
        if not await RequestRepository(ledger.postgres).exists(profile_id,body.request_id):
            raise HTTPException(status_code=404,detail="resource not found")
    run_id=await ledger.create_analysis_run("source_acquisition","task2-source-v1",request_id=body.request_id,profile_id=profile_id,configuration={"source":"upload"})
    snapshot_id=await ledger.create_export_snapshot(run_id,"manual_import",request_id=body.request_id,profile_id=profile_id,metadata={"file_name":path.name})
    _,artifact_id=await ledger.record_source_artifact(snapshot_id,path.read_bytes(),storage_uri=path.as_uri(),original_path=str(path),file_name=path.name,declared_mime=body.declared_mime,extension=path.suffix.lower() or None,file_type_status="declared" if body.declared_mime else "unknown",source_organisation=body.source_organisation)
    await ledger.postgres.execute("UPDATE analysis_runs SET status='completed',completed_at=NOW() WHERE id=$1",run_id)
    return {"analysis_run_id":str(run_id),"export_snapshot_id":str(snapshot_id),"source_artifact_id":str(artifact_id)}
