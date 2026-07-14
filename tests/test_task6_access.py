from uuid import uuid4
import pytest
from privacy.access import AccessEvidence,classify_storage,create_access_edge
from privacy.contracts import GraphEpistemicState,InstitutionalAccessType,InstitutionalStorageClass

def test_custody_access_and_linkability_classes_are_distinct():
    a,b=uuid4(),uuid4()
    assert classify_storage(AccessEvidence(central_storage_assertion_ids=(a,))) is InstitutionalStorageClass.CENTRALLY_STORED
    assert classify_storage(AccessEvidence(mutual_access_assertion_ids=(a,))) is InstitutionalStorageClass.FEDERATED_MUTUALLY_ACCESSIBLE
    assert classify_storage(AccessEvidence(independent_storage_assertion_ids=(a,),shared_identifier_assertion_ids=(b,))) is InstitutionalStorageClass.INDEPENDENTLY_STORED_LINKABLE
    assert classify_storage(AccessEvidence(shared_identifier_assertion_ids=(b,))) is InstitutionalStorageClass.UNKNOWN

def test_shared_identifier_never_creates_access():
    with pytest.raises(ValueError,match="linkability"):
        create_access_edge(source_ref="Organisation:a",target_ref="Dataset:b",
            access_type=InstitutionalAccessType.CONTROLS,assertion_id=uuid4(),
            epistemic_state=GraphEpistemicState.CURRENTLY_OBSERVED,identifier_overlap_only=True)

def test_all_edge_types_require_assertions():
    for kind in InstitutionalAccessType:
        with pytest.raises(ValueError,match="Assertion"):
            create_access_edge(source_ref="a",target_ref="b",access_type=kind,assertion_id=None,
                epistemic_state=GraphEpistemicState.ALLEGED_UNVERIFIED)

def test_supported_legal_gateway_keeps_instrument_and_requirements():
    assertion=uuid4()
    edge=create_access_edge(source_ref="Authority:ico",target_ref="Dataset:logs",
        access_type=InstitutionalAccessType.HAS_LEGAL_GATEWAY_TO,assertion_id=assertion,
        epistemic_state=GraphEpistemicState.CURRENTLY_OBSERVED,
        jurisdiction="GB",legal_instrument="Data Protection Act request power",
        requirements=("written notice","statutory threshold"),transparency="aggregate reporting")
    assert edge.assertion_id==assertion and edge.legal_instrument
    assert edge.requirements==("written notice","statutory threshold")

def test_gateway_without_instrument_remains_unestablished():
    with pytest.raises(ValueError,match="legal instrument"):
        create_access_edge(source_ref="authority",target_ref="dataset",
            access_type=InstitutionalAccessType.HAS_LEGAL_GATEWAY_TO,assertion_id=uuid4(),
            epistemic_state=GraphEpistemicState.POTENTIALLY_ENABLED)
