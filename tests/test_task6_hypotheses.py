from uuid import uuid4
import pytest
from privacy.contracts import HypothesisStatus
from privacy.hypotheses import EvidenceGap,ResolutionOutcome,detect_hypothesis,resolve_with_evidence

@pytest.mark.parametrize("gap_type",[
 "unknown_linkage_mechanism","missing_category_derivation","undefined_internal_identifier",
 "capability_implementation_unknown","deletion_conflict"])
def test_deterministic_gaps_create_uncertainty_not_graph_truth(gap_type):
    value=detect_hypothesis(profile_id=uuid4(),analysis_run_id=uuid4(),
      gap=EvidenceGap(gap_type,"opaque-17","controller",(uuid4(),)))
    assert value.status is HypothesisStatus.OPEN
    assert value.unresolved_question.endswith("?")
    assert "does not establish" in value.statement or "without" in value.statement or "conflicts" in value.statement

def test_targeted_question_requests_specific_missing_information():
    value=detect_hypothesis(profile_id=uuid4(),analysis_run_id=uuid4(),
      gap=EvidenceGap("missing_category_derivation","Interest:Travel","controller",(uuid4(),)))
    assert "source, derivation logic and inputs" in value.unresolved_question

def test_model_opinion_cannot_resolve_hypothesis():
    value=detect_hypothesis(profile_id=uuid4(),analysis_run_id=uuid4(),
      gap=EvidenceGap("unknown_linkage_mechanism","id","controller",(uuid4(),)))
    with pytest.raises(ValueError,match="model opinion"):
        resolve_with_evidence(value,outcome=ResolutionOutcome.CONFIRMED,evidence_assertion_ids=())
    unresolved=resolve_with_evidence(value,outcome=ResolutionOutcome.UNRESOLVED,evidence_assertion_ids=())
    assert unresolved.status is HypothesisStatus.UNRESOLVED

def test_new_assertion_can_confirm_or_reject():
    value=detect_hypothesis(profile_id=uuid4(),analysis_run_id=uuid4(),
      gap=EvidenceGap("capability_implementation_unknown","matching","controller",(uuid4(),)))
    assert resolve_with_evidence(value,outcome=ResolutionOutcome.CONFIRMED,
      evidence_assertion_ids=(uuid4(),)).status is HypothesisStatus.CONFIRMED
    assert resolve_with_evidence(value,outcome=ResolutionOutcome.REJECTED,
      evidence_assertion_ids=(uuid4(),)).status is HypothesisStatus.REJECTED
