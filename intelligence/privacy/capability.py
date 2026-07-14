"""Versioned deterministic capability-candidate engine."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
import json
from typing import Any,Mapping
from uuid import NAMESPACE_URL,UUID,uuid5

from db.postgres import PostgresClient,get_postgres_client
from .contracts import CapabilityCandidate,CapabilityExposureStatus,CapabilityKind

TAXONOMY_VERSION="task6-capability-taxonomy-v1"
RULE_VERSION="task6-capability-rules-v1"

@dataclass(frozen=True,slots=True)
class CapabilityRule:
    rule_id:str; capability:CapabilityKind; description:str
    required:Mapping[str,float]

RULES=(
 CapabilityRule("CAP-STABLE-ID-CROSS-SERVICE",CapabilityKind.CROSS_SERVICE_IDENTITY_RESOLUTION,"A stable identifier is observed across services",{"stable_identifier_service_count":2}),
 CapabilityRule("CAP-PRECISE-LOCATION-DENSITY",CapabilityKind.LOCATION_RECONSTRUCTION,"Precise location observations meet the reviewed temporal density",{"precise_location_count":3,"location_active_days":2}),
 CapabilityRule("CAP-BEHAVIOUR-CONTROLLER-LABEL",CapabilityKind.INTEREST_INFERENCE,"Behavioural history and controller labels co-occur",{"behavioural_event_count":1,"controller_label_count":1}),
 CapabilityRule("CAP-DIRECTIONAL-INTERACTION",CapabilityKind.SOCIAL_GRAPH_RECONSTRUCTION,"Directional interaction history is observed",{"directional_interaction_count":2}),
 CapabilityRule("CAP-AGE-LABEL",CapabilityKind.AGE_CLASSIFICATION,"An age or age-band classification is present",{"age_classification_count":1}),
 CapabilityRule("CAP-PURCHASE-HISTORY",CapabilityKind.PURCHASE_PROFILING,"Purchase history records are present",{"purchase_event_count":2}),
 CapabilityRule("CAP-PERSONALISATION",CapabilityKind.BEHAVIOURAL_PERSONALISATION,"Personalisation assignments co-occur with behavioural history",{"behavioural_event_count":1,"personalisation_assignment_count":1}),
 CapabilityRule("CAP-PREDICTION",CapabilityKind.BEHAVIOURAL_PREDICTION,"A controller prediction output is present",{"prediction_output_count":1}),
 CapabilityRule("CAP-BIOMETRIC",CapabilityKind.BIOMETRIC_MATCHING,"A biometric template or match record is present",{"biometric_record_count":1}),
 CapabilityRule("CAP-CONTENT-SCAN",CapabilityKind.COMMUNICATIONS_CONTENT_SCANNING,"Content scanning records are present",{"content_scan_record_count":1}),
 CapabilityRule("CAP-DEVICE-CORRELATION",CapabilityKind.DEVICE_CORRELATION,"A stable device identifier spans contexts",{"device_context_count":2}),
 CapabilityRule("CAP-SENSITIVE-INTEREST",CapabilityKind.SENSITIVE_INTEREST_INFERENCE,"A controller sensitive-interest assignment is present",{"sensitive_interest_label_count":1}),
 CapabilityRule("CAP-RISK-SCORE",CapabilityKind.RISK_SCORING,"A controller risk score record is present",{"risk_score_record_count":1}),
 CapabilityRule("CAP-AUTOMATED-RESTRICTION",CapabilityKind.AUTOMATED_ACCESS_RESTRICTION,"An automated restriction decision record is present",{"automated_restriction_count":1}),
)

class CapabilityCandidateEngine:
    def evaluate(self,*,profile_id:UUID,analysis_run_id:UUID,features:Mapping[str,float],
                 assertion_ids:tuple[UUID,...]=(),aggregate_ids:tuple[UUID,...]=(),
                 evidence_status:CapabilityExposureStatus=CapabilityExposureStatus.EVIDENCED_FROM_EXPORT,
                 human_confirmed:bool=False,calculated_at:datetime|None=None)->tuple[CapabilityCandidate,...]:
        if evidence_status in {CapabilityExposureStatus.EVIDENCED_FROM_EXPORT,CapabilityExposureStatus.DOCUMENTED,CapabilityExposureStatus.LEGALLY_AUTHORISED,CapabilityExposureStatus.HUMAN_CONFIRMED} and not assertion_ids:
            raise ValueError(f"{evidence_status.value} requires supporting assertions")
        if evidence_status is CapabilityExposureStatus.HUMAN_CONFIRMED and not human_confirmed:
            raise ValueError("human_confirmed status requires an explicit human confirmation")
        at=calculated_at or datetime.now(timezone.utc)
        results=[]
        for rule in RULES:
            observed={key:float(features.get(key,0)) for key in rule.required}
            passed=all(observed[key]>=minimum for key,minimum in rule.required.items())
            if not passed: continue
            rule_result={"passed":True,"observed":observed,"thresholds":dict(rule.required)}
            stable=f"{profile_id}:{rule.rule_id}:{RULE_VERSION}:{analysis_run_id}"
            results.append(CapabilityCandidate(
                id=uuid5(NAMESPACE_URL,stable),profile_id=profile_id,capability=rule.capability,
                rule_id=rule.rule_id,rule_version=RULE_VERSION,
                supporting_assertion_ids=tuple(sorted(assertion_ids,key=str)),
                supporting_aggregate_ids=tuple(sorted(aggregate_ids,key=str)),
                evidence_status=evidence_status,rule_result=rule_result,
                confidence=1.0,analysis_run_id=analysis_run_id,calculated_at=at,
            ))
        return tuple(results)

class CapabilityRepository:
    def __init__(self,postgres:PostgresClient|None=None): self.postgres=postgres or get_postgres_client()
    async def ensure_taxonomy(self)->None:
        for kind in CapabilityKind:
            label=kind.value.replace("_"," ").title()
            await self.postgres.execute(
                """INSERT INTO capability_taxonomy(capability_key,taxonomy_version,label,description)
                   VALUES($1,$2,$3,$4) ON CONFLICT(capability_key,taxonomy_version) DO NOTHING""",
                kind.value,TAXONOMY_VERSION,label,f"Reviewed deterministic taxonomy entry for {label}.")
    async def save(self,candidates:tuple[CapabilityCandidate,...])->None:
        await self.ensure_taxonomy()
        for item in candidates:
            await self.postgres.execute(
                """INSERT INTO capability_candidates(id,profile_id,capability_key,taxonomy_version,
                   rule_id,rule_version,supporting_assertion_ids,supporting_aggregate_ids,evidence_status,
                   rule_result,confidence,analysis_run_id,calculated_at)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12,$13)
                   ON CONFLICT(profile_id,capability_key,rule_id,rule_version,analysis_run_id) DO NOTHING""",
                item.id,item.profile_id,item.capability.value,TAXONOMY_VERSION,item.rule_id,item.rule_version,
                list(item.supporting_assertion_ids),list(item.supporting_aggregate_ids),item.evidence_status.value,
                json.dumps(item.rule_result,sort_keys=True),item.confidence,item.analysis_run_id,item.calculated_at)
