"""Auditable privacy uncertainty, targeted DSAR drafting and evidence resolution."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from enum import Enum
from uuid import NAMESPACE_URL,UUID,uuid5

from db.postgres import PostgresClient,get_postgres_client
from request_domain import RequestRepository
from .contracts import HypothesisStatus,PrivacyHypothesis

DETECTOR_VERSION="task6-hypothesis-detectors-v1"

@dataclass(frozen=True,slots=True)
class EvidenceGap:
    gap_type:str
    subject_ref:str
    controller_key:str
    supporting_assertion_ids:tuple[UUID,...]
    detail:str|None=None

_QUESTIONS={
 "unknown_linkage_mechanism":"How is identifier {subject} used to link records across your services, including the systems, purposes and recipients involved?",
 "missing_category_derivation":"What are the source, derivation logic and inputs for the assigned category {subject}?",
 "undefined_internal_identifier":"What does internal identifier {subject} reference, where is it used and what is its retention period?",
 "capability_implementation_unknown":"Is capability {subject} currently implemented, and if so, what are its processing purpose, data inputs and safeguards?",
 "deletion_conflict":"Why does {subject} remain present in the later export after the deletion response, and which systems and retention basis are relevant?",
}

def detect_hypothesis(*,profile_id:UUID,analysis_run_id:UUID,gap:EvidenceGap,
                      now:datetime|None=None)->PrivacyHypothesis:
    if gap.gap_type not in _QUESTIONS: raise ValueError("unsupported deterministic evidence gap")
    if not gap.supporting_assertion_ids: raise ValueError("hypotheses require supporting evidence")
    question=_QUESTIONS[gap.gap_type].format(subject=gap.subject_ref)
    statement={
      "unknown_linkage_mechanism":"A stable identifier appears across datasets, but available evidence does not establish the linkage mechanism.",
      "missing_category_derivation":"A controller-assigned category appears in available evidence without its derivation.",
      "undefined_internal_identifier":"An internal identifier appears in available evidence without a definition.",
      "capability_implementation_unknown":"A capability candidate exists, but available evidence does not establish current implementation.",
      "deletion_conflict":"A later observed export conflicts with the expected removal.",
    }[gap.gap_type]
    at=now or datetime.now(timezone.utc)
    stable=f"{profile_id}:{gap.gap_type}:{gap.subject_ref}:{DETECTOR_VERSION}:{analysis_run_id}"
    return PrivacyHypothesis(id=uuid5(NAMESPACE_URL,stable),profile_id=profile_id,
      detector_id=f"privacy-gap:{gap.gap_type}",detector_version=DETECTOR_VERSION,
      statement=statement,unresolved_question=question,status=HypothesisStatus.OPEN,
      supporting_assertion_ids=tuple(sorted(gap.supporting_assertion_ids,key=str)),
      created_at=at,updated_at=at)

class ResolutionOutcome(str,Enum):
    CONFIRMED="confirmed"; REJECTED="rejected"; UNRESOLVED="unresolved"; SUPERSEDED="superseded"

def resolve_with_evidence(hypothesis:PrivacyHypothesis,*,outcome:ResolutionOutcome,
                          evidence_assertion_ids:tuple[UUID,...],at:datetime|None=None)->PrivacyHypothesis:
    if hypothesis.status not in {HypothesisStatus.OPEN,HypothesisStatus.REQUEST_DRAFTED,
                                 HypothesisStatus.REQUEST_SENT,HypothesisStatus.UNRESOLVED}:
        raise ValueError("terminal hypothesis cannot be resolved again")
    if outcome is not ResolutionOutcome.UNRESOLVED and not evidence_assertion_ids:
        raise ValueError("model opinion alone cannot resolve a hypothesis")
    return hypothesis.model_copy(update={"status":HypothesisStatus(outcome.value),"updated_at":at or datetime.now(timezone.utc)})

class HypothesisRepository:
    def __init__(self,postgres:PostgresClient|None=None):
        self.postgres=postgres or get_postgres_client()
        self.requests=RequestRepository(self.postgres)
    async def save(self,value:PrivacyHypothesis,analysis_run_id:UUID)->None:
        await self.postgres.execute("""INSERT INTO privacy_hypotheses(id,profile_id,detector_id,detector_version,
          statement,unresolved_question,status,supporting_assertion_ids,request_id,supersedes_id,analysis_run_id,
          created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT(id) DO NOTHING""",
          value.id,value.profile_id,value.detector_id,value.detector_version,value.statement,value.unresolved_question,
          value.status.value,list(value.supporting_assertion_ids),value.request_id,value.supersedes_id,
          analysis_run_id,value.created_at,value.updated_at)
    async def draft_targeted_request(self,value:PrivacyHypothesis,*,company_name:str,company_url:str|None=None)->PrivacyHypothesis:
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection,connection.transaction():
            row=await connection.fetchrow("SELECT status,request_id FROM privacy_hypotheses WHERE id=$1 FOR UPDATE",value.id)
            if not row: raise LookupError("privacy hypothesis does not exist")
            if row["request_id"]: request_id=row["request_id"]
            else:
                request_id=await self.requests.create_draft(
                  value.profile_id,company_name=company_name,company_url=company_url,
                  domain=company_name.casefold(),request_type="access",
                  notes=f"Targeted evidence question:\n{value.unresolved_question}",connection=connection)
                await connection.execute("""UPDATE privacy_hypotheses SET status='request_drafted',request_id=$2,
                  updated_at=NOW() WHERE id=$1""",value.id,request_id)
                await connection.execute("""INSERT INTO privacy_hypothesis_transitions(hypothesis_id,status_before,
                  status_after,evidence_assertion_ids,actor) VALUES($1,$2,'request_drafted','{}','system:targeted-dsar')""",
                  value.id,row["status"])
        return value.model_copy(update={"status":HypothesisStatus.REQUEST_DRAFTED,"request_id":request_id,
                                        "updated_at":datetime.now(timezone.utc)})
    async def transition(self,before:PrivacyHypothesis,after:PrivacyHypothesis,
                         evidence_assertion_ids:tuple[UUID,...],actor:str)->None:
        await self.postgres.execute("""INSERT INTO privacy_hypothesis_transitions(hypothesis_id,status_before,
          status_after,evidence_assertion_ids,actor) VALUES($1,$2,$3,$4,$5)""",
          before.id,before.status.value,after.status.value,list(evidence_assertion_ids),actor)
        await self.postgres.execute("UPDATE privacy_hypotheses SET status=$2,updated_at=$3 WHERE id=$1",
          before.id,after.status.value,after.updated_at)
