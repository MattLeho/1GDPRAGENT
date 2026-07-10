"""Compatibility adapter from legacy KG ingestion to the canonical assertion ledger.

This module deliberately does not write Neo4j. Model output is recorded as reviewable
candidate assertions and can only reach the graph through GraphProjectionService after
the ledger's provenance and lifecycle guards accept it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from evidence.ledger import EvidenceLedger
from evidence.models import (
    AssertionCreate, AssertionStatus, DataClass, EpistemicBasis,
    EvidenceLocatorCreate, LocatorType,
)


@dataclass
class IngestRequest:
    company_name: str
    request_id: str
    extracted_data: list[dict]=field(default_factory=list)
    categories: dict=field(default_factory=dict)
    source: str="manual"
    source_artifact: dict[str,Any]=field(default_factory=dict)


@dataclass
class IngestResult:
    success: bool
    request_id: str
    company_name: str
    total_items: int
    statements_executed: int
    statements_errored: int
    errors: list[str]=field(default_factory=list)
    candidate_assertion_ids: list[str]=field(default_factory=list)


class KGIngestorAgent:
    """Legacy-shaped ingestion facade backed by the immutable evidence ledger."""

    async def ingest(self, request: IngestRequest) -> IngestResult:
        ledger=EvidenceLedger(); errors=[]; assertion_ids=[]
        try: request_uuid=UUID(request.request_id)
        except (ValueError,TypeError): request_uuid=None
        run_id=await ledger.create_analysis_run("legacy_kg_ingestion_adapter","task1-kg-adapter-v1",request_id=request_uuid,configuration={"source":request.source,"model_output":True,"legacy_file_id":str(request.source_artifact.get("legacy_file_id") or request.source_artifact.get("file_id") or "")})
        artifact_id=None; source_bytes=None
        try:
            artifact_id,source_bytes=await self._record_source(request,ledger,run_id,request_uuid)
        except Exception as exc:
            errors.append(f"source artifact not recorded: {exc}")

        for item in request.extracted_data:
            value=str(item.get("value") or item.get("text") or "").strip()
            if not value: continue
            locator_ids=[]
            if artifact_id and source_bytes:
                needle=value.encode("utf-8"); start=source_bytes.find(needle)
                if start>=0:
                    locator_id=await ledger.create_locator(EvidenceLocatorCreate(artifact_id=artifact_id,locator_type=LocatorType.TEXT_SPAN,locator={"byte_start":start,"byte_end":start+len(needle)},expected_text=value),source_bytes)
                    locator_ids.append(locator_id)
            data_class=DataClass.INFERRED if str(item.get("category","")).upper()=="INFERRED" else DataClass.DERIVED
            try:
                assertion_id=await ledger.create_assertion(AssertionCreate(
                    subject_type="ControllerProfile",subject_ref=f"{request.company_name}:{request.request_id}",
                    predicate="ASSIGNED_ATTRIBUTE",object_type="literal",object_value={"value":value,"type":str(item.get("type") or "unknown"),"category":str(item.get("category") or "unknown")},
                    assertion_type="hypothesis",data_class=data_class,status=AssertionStatus.CANDIDATE,
                    epistemic_basis=EpistemicBasis.MODEL_HYPOTHESIS,confidence=self._confidence(item.get("confidence")),
                    ingested_at=datetime.now(timezone.utc),derivation_method="legacy_model_extraction_adapter",
                    derivation_version="task1-kg-adapter-v1",analysis_run_id=run_id,evidence_locator_ids=tuple(locator_ids)))
                assertion_ids.append(str(assertion_id))
            except Exception as exc: errors.append(str(exc))

        await ledger.postgres.execute("UPDATE analysis_runs SET status=$2,completed_at=NOW(),error=$3 WHERE id=$1",run_id,"completed" if not errors else "failed","; ".join(errors) or None)
        return IngestResult(success=not errors,request_id=request.request_id,company_name=request.company_name,total_items=len(request.extracted_data),statements_executed=0,statements_errored=len(errors),errors=errors,candidate_assertion_ids=assertion_ids)

    async def _record_source(self, request: IngestRequest, ledger: EvidenceLedger, run_id: UUID, request_id: UUID | None):
        details=request.source_artifact or {}; legacy_id=details.get("legacy_file_id") or details.get("file_id")
        row=None
        if legacy_id:
            rows=await ledger.postgres.execute("SELECT * FROM received_data WHERE id=$1::uuid",str(legacy_id)); row=dict(rows[0]) if rows else None
        raw_path=Path(str(row.get("file_path"))) if row and row.get("file_path") else None
        shared_path=None
        if raw_path:
            normalized=str(raw_path).replace("\\","/")
            if normalized.startswith("/app/uploads/"):
                shared_path=Path("/source-uploads")/normalized.removeprefix("/app/uploads/")
        path=raw_path if raw_path and raw_path.is_file() else shared_path
        if path and path.is_file():
            content=path.read_bytes(); storage_uri=path.resolve().as_uri(); original_path=str(raw_path)
        elif details.get("exact_text") is not None:
            content=str(details["exact_text"]).encode(); storage_uri=f"legacy-extracted-text://{legacy_id or run_id}"; original_path=str(row.get("file_name") if row else legacy_id or "legacy-extracted-text")
        else: return None,None
        snapshot_id=await ledger.create_export_snapshot(run_id,"dsar_response" if request_id else "manual_import",request_id=request_id,controller_key=request.company_name,metadata={"legacy_file_id":str(legacy_id) if legacy_id else None})
        _,artifact_id=await ledger.record_source_artifact(snapshot_id,content,storage_uri=storage_uri,original_path=original_path,file_name=str(row.get("file_name") if row else Path(original_path).name),declared_mime=str(row.get("file_type") or "") if row else None,extension=Path(original_path).suffix.lower() or None,file_type_status="declared",source_organisation=request.company_name)
        return artifact_id,content

    @staticmethod
    def _confidence(value: Any) -> float | None:
        if isinstance(value,(int,float)): return max(0.0,min(1.0,float(value)))
        return {"LOW":0.35,"MEDIUM":0.6,"HIGH":0.85}.get(str(value).upper())


async def ingest_to_graph(company_name: str, request_id: str, extracted_data: list[dict], categories: dict | None=None, source: str="manual") -> IngestResult:
    return await KGIngestorAgent().ingest(IngestRequest(company_name=company_name,request_id=request_id,extracted_data=extracted_data,categories=categories or {},source=source))
