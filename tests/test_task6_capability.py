from uuid import uuid4
import pytest
from privacy.capability import CapabilityCandidateEngine,RULES
from privacy.contracts import CapabilityExposureStatus,CapabilityKind

def test_taxonomy_has_all_required_capabilities():
    assert {r.capability for r in RULES}==set(CapabilityKind)

def test_four_primary_rules_are_deterministic_and_grounded():
    assertion=uuid4(); aggregate=uuid4(); run=uuid4(); profile=uuid4()
    features={"stable_identifier_service_count":3,"precise_location_count":8,"location_active_days":4,
              "behavioural_event_count":7,"controller_label_count":1,"directional_interaction_count":9}
    left=CapabilityCandidateEngine().evaluate(profile_id=profile,analysis_run_id=run,features=features,
        assertion_ids=(assertion,),aggregate_ids=(aggregate,))
    right=CapabilityCandidateEngine().evaluate(profile_id=profile,analysis_run_id=run,features=features,
        assertion_ids=(assertion,),aggregate_ids=(aggregate,))
    keys={item.capability for item in left}
    assert {CapabilityKind.CROSS_SERVICE_IDENTITY_RESOLUTION,CapabilityKind.LOCATION_RECONSTRUCTION,
            CapabilityKind.INTEREST_INFERENCE,CapabilityKind.SOCIAL_GRAPH_RECONSTRUCTION}<=keys
    assert [x.id for x in left]==[x.id for x in right]
    assert all(x.supporting_assertion_ids==(assertion,) and x.rule_result["passed"] for x in left)

def test_thresholds_do_not_emit_candidates():
    assert CapabilityCandidateEngine().evaluate(profile_id=uuid4(),analysis_run_id=uuid4(),
        features={},evidence_status=CapabilityExposureStatus.TECHNICALLY_POSSIBLE)==()

def test_status_promotion_requires_defined_evidence_standard():
    with pytest.raises(ValueError,match="supporting assertions"):
        CapabilityCandidateEngine().evaluate(profile_id=uuid4(),analysis_run_id=uuid4(),features={"risk_score_record_count":1})
    with pytest.raises(ValueError,match="human confirmation"):
        CapabilityCandidateEngine().evaluate(profile_id=uuid4(),analysis_run_id=uuid4(),
            features={"risk_score_record_count":1},assertion_ids=(uuid4(),),
            evidence_status=CapabilityExposureStatus.HUMAN_CONFIRMED)

def test_technical_possibility_is_not_observed_implementation():
    item=CapabilityCandidateEngine().evaluate(profile_id=uuid4(),analysis_run_id=uuid4(),
        features={"device_context_count":2},evidence_status=CapabilityExposureStatus.TECHNICALLY_POSSIBLE)[0]
    assert item.evidence_status is CapabilityExposureStatus.TECHNICALLY_POSSIBLE
    assert item.capability is CapabilityKind.DEVICE_CORRELATION
