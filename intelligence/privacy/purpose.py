"""Grounded purpose lineage and non-legal purpose-distance assessment."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any,Literal
from uuid import NAMESPACE_URL,UUID,uuid5

from db.postgres import PostgresClient,get_postgres_client
from .contracts import Claim,Purpose,PurposeDistance,PurposeDistanceAssessment

HEURISTIC_VERSION="task6-purpose-distance-v1"
PurposeRelation=Literal["ORIGINALLY_JUSTIFIED_BY","CURRENT_SCOPE","TECHNICALLY_COULD_ENABLE"]

@dataclass(frozen=True,slots=True)
class CapabilityPurposeLink:
    capability_ref:str; relation:PurposeRelation; target_ref:str; assertion_ids:tuple[UUID,...]
    def __post_init__(self):
        if not self.assertion_ids: raise ValueError("purpose lineage links require supporting assertions")

def grounded_claim(*,claim_id:UUID,claim_type:str,text:str,source_artifact_id:UUID,
                   evidence_locator_ids:tuple[UUID,...],status:Literal["candidate","accepted","rejected","superseded"]="candidate",
                   valid_from:datetime|None=None,valid_to:datetime|None=None)->Claim:
    if not text.strip(): raise ValueError("claim text is required")
    if not evidence_locator_ids: raise ValueError("grounded claims require exact EvidenceLocators")
    if valid_from and valid_to and valid_to<valid_from: raise ValueError("claim validity window is reversed")
    return Claim(id=claim_id,claim_type=claim_type,text=text.strip(),source_artifact_id=source_artifact_id,
                 evidence_locator_ids=evidence_locator_ids,status=status,valid_from=valid_from,valid_to=valid_to)

def assess_purpose_distance(*,original:Purpose,current:Purpose,features:dict[str,Any],
                            analysis_run_id:UUID,assertion_ids:tuple[UUID,...])->PurposeDistanceAssessment:
    """Apply explicit, reproducible v1 features; never determine legality."""
    same=original.purpose_key==current.purpose_key
    if same: distance=PurposeDistance.SAME
    elif features.get("same_core_outcome") is True and features.get("same_data_domain") is True:
        distance=PurposeDistance.CLOSELY_COMPATIBLE
    elif features.get("shared_context") is True or features.get("shared_recipient") is True:
        distance=PurposeDistance.ADJACENT
    elif features.get("new_data_domain") is True or features.get("new_decision_effect") is True:
        distance=PurposeDistance.MATERIALLY_DIFFERENT
    else: distance=PurposeDistance.UNRELATED
    stable=f"{original.id}:{current.id}:{HEURISTIC_VERSION}:{analysis_run_id}"
    return PurposeDistanceAssessment(id=uuid5(NAMESPACE_URL,stable),original_purpose_id=original.id,
        current_purpose_id=current.id,distance=distance,heuristic_version=HEURISTIC_VERSION,
        feature_vector=dict(features),wording="Possible purpose drift",assertion_ids=assertion_ids,
        analysis_run_id=analysis_run_id)

class PurposeRepository:
    def __init__(self,postgres:PostgresClient|None=None): self.postgres=postgres or get_postgres_client()
    async def save_purpose(self,value:Purpose)->None:
        await self.postgres.execute("""INSERT INTO privacy_purposes(id,purpose_key,label,description,valid_from,valid_to)
          VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(purpose_key,valid_from) DO NOTHING""",
          value.id,value.purpose_key,value.label,value.description,value.valid_from,value.valid_to)
    async def save_claim(self,claim:Claim,*,policy_source_version_id:UUID,analysis_run_id:UUID)->None:
        await self.postgres.execute("""INSERT INTO policy_claims(id,policy_source_version_id,claim_type,claim_text,status,
          evidence_locator_ids,valid_from,valid_to,analysis_run_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(id) DO NOTHING""",
          claim.id,policy_source_version_id,claim.claim_type,claim.text,claim.status,list(claim.evidence_locator_ids),
          claim.valid_from,claim.valid_to,analysis_run_id)
    async def save_assessment(self,value:PurposeDistanceAssessment)->None:
        await self.postgres.execute("""INSERT INTO purpose_distance_assessments(id,original_purpose_id,current_purpose_id,
          distance,heuristic_version,feature_vector,wording,assertion_ids,analysis_run_id)
          VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9)
          ON CONFLICT(original_purpose_id,current_purpose_id,heuristic_version,analysis_run_id) DO NOTHING""",
          value.id,value.original_purpose_id,value.current_purpose_id,int(value.distance),value.heuristic_version,
          json.dumps(value.feature_vector,sort_keys=True),value.wording,list(value.assertion_ids),value.analysis_run_id)
