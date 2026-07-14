"""Frozen Task 6 ontology, epistemic and query contracts."""
from __future__ import annotations
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class FrozenModel(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid")

class CapabilityExposureStatus(str,Enum):
    EVIDENCED_FROM_EXPORT="evidenced_from_export"; DOCUMENTED="documented"
    LEGALLY_AUTHORISED="legally_authorised"; TECHNICALLY_POSSIBLE="technically_possible"
    SPECULATIVE="speculative"; HUMAN_CONFIRMED="human_confirmed"
class GraphEpistemicState(str,Enum):
    CURRENTLY_OBSERVED="currently_observed"; POTENTIALLY_ENABLED="potentially_enabled"
    ALLEGED_UNVERIFIED="alleged_unverified"
class ProfileLayer(str,Enum):
    SELF_DECLARED="self_declared"; OBSERVED_BEHAVIOUR="observed_behaviour"
    CONTROLLER_PROFILE="controller_profile"; SYSTEM_HYPOTHESES="system_hypotheses"
class HypothesisStatus(str,Enum):
    OPEN="open"; REQUEST_DRAFTED="request_drafted"; REQUEST_SENT="request_sent"
    CONFIRMED="confirmed"; REJECTED="rejected"; UNRESOLVED="unresolved"; SUPERSEDED="superseded"
class DeletionVerificationStatus(str,Enum):
    EXPECTED_REMOVED="EXPECTED_REMOVED"
    CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT="CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT"
    STILL_OBSERVED="STILL_OBSERVED"; UNVERIFIABLE="UNVERIFIABLE"
class InstitutionalStorageClass(str,Enum):
    CENTRALLY_STORED="centrally_stored"; FEDERATED_MUTUALLY_ACCESSIBLE="federated_mutually_accessible"
    INDEPENDENTLY_STORED_LINKABLE="independently_stored_linkable"; UNKNOWN="unknown"
class InstitutionalAccessType(str,Enum):
    CONTROLS="CONTROLS"; PROCESSES="PROCESSES"; HOSTS="HOSTS"; CAN_REQUEST="CAN_REQUEST"
    HAS_LEGAL_GATEWAY_TO="HAS_LEGAL_GATEWAY_TO"; SHARES_WITH="SHARES_WITH"
    USES_SUBPROCESSOR="USES_SUBPROCESSOR"
class PurposeDistance(IntEnum):
    SAME=0; CLOSELY_COMPATIBLE=1; ADJACENT=2; MATERIALLY_DIFFERENT=3; UNRELATED=4
class CapabilityKind(str,Enum):
    AGE_CLASSIFICATION="age_classification"
    CROSS_SERVICE_IDENTITY_RESOLUTION="cross_service_identity_resolution"
    LOCATION_RECONSTRUCTION="location_reconstruction"
    SOCIAL_GRAPH_RECONSTRUCTION="social_graph_reconstruction"
    PURCHASE_PROFILING="purchase_profiling"
    BEHAVIOURAL_PERSONALISATION="behavioural_personalisation"
    BEHAVIOURAL_PREDICTION="behavioural_prediction"
    BIOMETRIC_MATCHING="biometric_matching"
    COMMUNICATIONS_CONTENT_SCANNING="communications_content_scanning"
    DEVICE_CORRELATION="device_correlation"; INTEREST_INFERENCE="interest_inference"
    SENSITIVE_INTEREST_INFERENCE="sensitive_interest_inference"; RISK_SCORING="risk_scoring"
    AUTOMATED_ACCESS_RESTRICTION="automated_access_restriction"

class Capability(FrozenModel):
    id:UUID; capability_key:CapabilityKind; taxonomy_version:str; label:str; description:str
class CapabilityExposureState(FrozenModel):
    capability_id:UUID; status:CapabilityExposureStatus; assertion_ids:tuple[UUID,...]=()
    valid_from:datetime|None=None; valid_to:datetime|None=None; analysis_run_id:UUID
class CapabilityCandidate(FrozenModel):
    id:UUID; profile_id:UUID; capability:CapabilityKind; rule_id:str; rule_version:str
    supporting_assertion_ids:tuple[UUID,...]=(); supporting_aggregate_ids:tuple[UUID,...]=()
    evidence_status:CapabilityExposureStatus; rule_result:dict[str,Any]
    confidence:float|None=Field(default=None,ge=0,le=1); analysis_run_id:UUID; calculated_at:datetime
class EdgeRisk(FrozenModel):
    linkage_type:str; directness:float=Field(ge=0,le=1); stability:float=Field(ge=0,le=1)
    cross_context_reuse:float=Field(ge=0,le=1); uniqueness_gain:float=Field(ge=0,le=1)
    legal_accessibility:float|None=Field(default=None,ge=0,le=1)
    reversibility:float=Field(ge=0,le=1); confidence:float=Field(ge=0,le=1)
class IdentifierStatistic(FrozenModel):
    identifier_node_id:UUID; controller_count:int=Field(ge=0); service_count:int=Field(ge=0)
    data_domain_count:int=Field(ge=0); schema_count:int=Field(ge=0)
    first_seen:datetime|None=None; last_seen:datetime|None=None
    temporal_persistence_seconds:float=Field(ge=0); occurrence_count:int=Field(ge=0)
    degree:float=Field(ge=0); betweenness:float=Field(ge=0); articulation_point:bool=False
class LinkabilitySnapshot(FrozenModel):
    id:UUID; profile_id:UUID; graph_version:str; method:str; method_version:str
    node_ids:tuple[UUID,...]; edge_assertion_ids:tuple[UUID,...]
    identifier_statistics:tuple[IdentifierStatistic,...]; calculated_at:datetime
class IdentifierRemovalSimulation(FrozenModel):
    id:UUID; linkability_snapshot_id:UUID; graph_version:str
    selected_identifier_node_ids:tuple[UUID,...]=Field(min_length=1); calculation_method:str
    connected_components_before:int=Field(ge=0); connected_components_after:int=Field(ge=0)
    cross_domain_paths_before:int=Field(ge=0); cross_domain_paths_after:int=Field(ge=0)
    disconnected_path_fraction:float=Field(ge=0,le=1); calculated_at:datetime
class Purpose(FrozenModel):
    id:UUID; purpose_key:str; label:str; description:str|None=None
    valid_from:datetime|None=None; valid_to:datetime|None=None
class Claim(FrozenModel):
    id:UUID; claim_type:str; text:str; source_artifact_id:UUID
    evidence_locator_ids:tuple[UUID,...]=Field(min_length=1)
    status:Literal["candidate","accepted","rejected","superseded"]
    valid_from:datetime|None=None; valid_to:datetime|None=None
class PurposeDistanceAssessment(FrozenModel):
    id:UUID; original_purpose_id:UUID; current_purpose_id:UUID; distance:PurposeDistance
    heuristic_version:str; feature_vector:dict[str,Any]
    wording:Literal["Possible purpose drift"]="Possible purpose drift"
    assertion_ids:tuple[UUID,...]=(); analysis_run_id:UUID
class Dataset(FrozenModel):
    id:UUID; dataset_key:str; label:str; storage_class:InstitutionalStorageClass=InstitutionalStorageClass.UNKNOWN
class Authority(FrozenModel):
    id:UUID; authority_key:str; name:str; jurisdiction:str|None=None
class InstitutionalAccessEdge(FrozenModel):
    id:UUID; source_ref:str; target_ref:str; access_type:InstitutionalAccessType
    epistemic_state:GraphEpistemicState; assertion_id:UUID; jurisdiction:str|None=None
    legal_instrument:str|None=None; requirements:tuple[str,...]=(); transparency:str|None=None
class PrivacyHypothesis(FrozenModel):
    id:UUID; profile_id:UUID; detector_id:str; detector_version:str; statement:str
    unresolved_question:str; status:HypothesisStatus=HypothesisStatus.OPEN
    supporting_assertion_ids:tuple[UUID,...]=(); request_id:UUID|None=None
    supersedes_id:UUID|None=None; created_at:datetime; updated_at:datetime
class ExpectedRemoval(FrozenModel):
    id:UUID; deletion_simulation_id:UUID; object_type:str; object_ref:str
    expected_effect:str; evidence_assertion_ids:tuple[UUID,...]=()
class DeletionSimulation(FrozenModel):
    id:UUID; profile_id:UUID; graph_snapshot_id:UUID; method:str; method_version:str
    deletion_plan_id:UUID|None=None; selected_identifier_node_ids:tuple[UUID,...]=()
    predicted_effects:dict[str,Any]; expected_removals:tuple[ExpectedRemoval,...]=()
    calculated_at:datetime
class DeletionVerification(FrozenModel):
    id:UUID; expected_removal_id:UUID; later_export_snapshot_id:UUID
    status:DeletionVerificationStatus; observed_assertion_ids:tuple[UUID,...]=()
    checked_at:datetime; explanation:str
class PrivacyQueryCitation(FrozenModel):
    assertion_id:UUID; evidence_locator_ids:tuple[UUID,...]=Field(min_length=1)
    source_artifact_ids:tuple[UUID,...]=Field(min_length=1); excerpt:str|None=None
class PrivacyQueryResult(FrozenModel):
    tool:str; data:dict[str,Any]; citations:tuple[PrivacyQueryCitation,...]=()
    unknowns:tuple[str,...]=(); evidence_bearing:bool=True
    @model_validator(mode="after")
    def cited(self):
        if self.evidence_bearing and not self.citations:
            raise ValueError("evidence-bearing privacy results require resolvable citations")
        return self
