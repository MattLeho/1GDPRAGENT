from uuid import uuid4
import pytest
from privacy.contracts import Purpose,PurposeDistance
from privacy.purpose import CapabilityPurposeLink,assess_purpose_distance,grounded_claim

def purpose(key): return Purpose(id=uuid4(),purpose_key=key,label=key)

def test_claim_requires_exact_grounding_and_preserves_unknown_dates():
    with pytest.raises(ValueError,match="EvidenceLocators"):
        grounded_claim(claim_id=uuid4(),claim_type="purpose",text="analytics",source_artifact_id=uuid4(),evidence_locator_ids=())
    claim=grounded_claim(claim_id=uuid4(),claim_type="purpose",text=" analytics ",source_artifact_id=uuid4(),evidence_locator_ids=(uuid4(),))
    assert claim.text=="analytics" and claim.valid_from is None and claim.status=="candidate"

@pytest.mark.parametrize(("features","expected"),[
 ({"same_core_outcome":True,"same_data_domain":True},PurposeDistance.CLOSELY_COMPATIBLE),
 ({"shared_context":True},PurposeDistance.ADJACENT),
 ({"new_data_domain":True},PurposeDistance.MATERIALLY_DIFFERENT),
 ({},PurposeDistance.UNRELATED)])
def test_versioned_distance_is_not_a_legal_conclusion(features,expected):
    value=assess_purpose_distance(original=purpose("service"),current=purpose("advertising"),
        features=features,analysis_run_id=uuid4(),assertion_ids=(uuid4(),))
    assert value.distance is expected and value.wording=="Possible purpose drift"
    assert "violation" not in value.wording.casefold()

def test_same_purpose_is_zero():
    original=purpose("security")
    current=Purpose(id=uuid4(),purpose_key="security",label="other wording")
    assert assess_purpose_distance(original=original,current=current,features={},
        analysis_run_id=uuid4(),assertion_ids=()).distance is PurposeDistance.SAME

def test_lineage_relations_are_distinct_and_grounded():
    assertion=uuid4()
    links={CapabilityPurposeLink("cap","ORIGINALLY_JUSTIFIED_BY","claim", (assertion,)),
           CapabilityPurposeLink("cap","CURRENT_SCOPE","activity",(assertion,)),
           CapabilityPurposeLink("cap","TECHNICALLY_COULD_ENABLE","possible",(assertion,))}
    assert {x.relation for x in links}=={"ORIGINALLY_JUSTIFIED_BY","CURRENT_SCOPE","TECHNICALLY_COULD_ENABLE"}
