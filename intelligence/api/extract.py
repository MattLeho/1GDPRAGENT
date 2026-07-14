"""Canonical, routed grounded-claim ingestion.

Model execution is intentionally absent.  The frontend Task Router may supply
candidate exact quotes; this API verifies each quote against canonical bytes
and persists only resolvable policy Claims.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.security import require_internal_request, require_profile_id
from privacy.policy_sources import (
    PolicySourceIngestionService, PolicySourceMetadata, PolicyTextSpan,
)
from privacy.purpose import PurposeRepository, grounded_claim

router = APIRouter(
    prefix="/extract", tags=["Grounded extraction"],
    dependencies=[Depends(require_internal_request)],
)


class CandidateClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: str = Field(min_length=1, max_length=200)
    exact_quote: str = Field(min_length=1)
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)


class PolicyClaimsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1)
    policy_key: str = Field(min_length=1, max_length=500)
    version_label: str = Field(min_length=1, max_length=200)
    retrieved_at: datetime
    authorisation_basis: str = Field(min_length=1, max_length=1000)
    source_uri: str | None = None
    controller_key: str | None = None
    file_name: str = Field(default="privacy-policy.txt", min_length=1)
    claims: tuple[CandidateClaim, ...] = Field(default=(), max_length=500)


@router.post("/policy-claims")
async def ingest_policy_claims(
    body: PolicyClaimsRequest,
    profile_id: Annotated[UUID, Depends(require_profile_id)],
):
    raw = body.content.encode("utf-8")
    spans = tuple(PolicyTextSpan(
        byte_start=item.byte_start, byte_end=item.byte_end, expected_text=item.exact_quote,
    ) for item in body.claims)
    metadata = PolicySourceMetadata(
        policy_key=body.policy_key, version_label=body.version_label,
        retrieved_at=body.retrieved_at, authorisation_basis=body.authorisation_basis,
        source_uri=body.source_uri, file_name=body.file_name, profile_id=profile_id,
        controller_key=body.controller_key,
        extra={"candidate_claim_count": len(body.claims), "task_router_required": True},
    )
    try:
        source = await PolicySourceIngestionService().ingest(raw, metadata, text_spans=spans)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    postgres = PurposeRepository().postgres
    saved = []
    for candidate in body.claims:
        locator = {"byte_start": candidate.byte_start, "byte_end": candidate.byte_end}
        digest = sha256(raw[candidate.byte_start:candidate.byte_end]).hexdigest()
        rows = await postgres.execute(
            """SELECT id FROM evidence_locators WHERE artifact_id=$1 AND locator_type='text_span'
               AND locator=$2::jsonb AND raw_hash=$3 AND verified=true ORDER BY created_at,id LIMIT 1""",
            source.source_artifact_id, json.dumps(locator), digest,
        )
        if not rows:
            raise HTTPException(status_code=422, detail="candidate quote has no resolvable exact EvidenceLocator")
        claim_id = uuid5(NAMESPACE_URL, f"{source.policy_source_version_id}:{candidate.claim_type}:{candidate.byte_start}:{candidate.byte_end}")
        claim = grounded_claim(
            claim_id=claim_id, claim_type=candidate.claim_type, text=candidate.exact_quote,
            source_artifact_id=source.source_artifact_id,
            evidence_locator_ids=(rows[0]["id"],), status="candidate",
        )
        await PurposeRepository(postgres).save_claim(
            claim, policy_source_version_id=source.policy_source_version_id,
            analysis_run_id=source.analysis_run_id,
        )
        saved.append(claim.model_dump(mode="json"))
    return {"source": source.model_dump(mode="json"), "claims": saved,
            "grounding": "Every candidate quote was resolved against canonical UTF-8 bytes; no model was called by this API."}


@router.get("/health")
async def extract_health():
    return {"mode": "task-router-candidates-only", "direct_model_execution": False,
            "canonical_source_required": True, "exact_locator_required": True}
