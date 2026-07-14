from datetime import datetime,timezone
from uuid import uuid4
import pytest

from intelligence.privacy.access import create_access_edge
from intelligence.privacy.capability import CapabilityCandidateEngine
from intelligence.privacy.contracts import (
    CapabilityExposureStatus, CapabilityKind, DeletionVerificationStatus,
    GraphEpistemicState, InstitutionalAccessType, PrivacyQueryResult,
)
from intelligence.privacy.deletion import DeletionImpactInputs,LaterExportObservation,build_deletion_simulation,verify_later_export
from intelligence.privacy.hypotheses import EvidenceGap,ResolutionOutcome,detect_hypothesis,resolve_with_evidence
from intelligence.privacy.contracts import IdentifierRemovalSimulation


def test_synthetic_capability_layer_distinguishes_observed_documented_and_possible():
    ids=(uuid4(),); common=dict(profile_id=uuid4(),analysis_run_id=uuid4(),assertion_ids=ids)
    observed=CapabilityCandidateEngine().evaluate(features={"stable_identifier_service_count":3},**common)[0]
    documented=CapabilityCandidateEngine().evaluate(features={"precise_location_count":5,"location_active_days":3},
        evidence_status=CapabilityExposureStatus.DOCUMENTED,**common)[0]
    possible=CapabilityCandidateEngine().evaluate(features={"device_context_count":2},
        evidence_status=CapabilityExposureStatus.TECHNICALLY_POSSIBLE,**common)[0]
    assert observed.capability is CapabilityKind.CROSS_SERVICE_IDENTITY_RESOLUTION
    assert documented.evidence_status is CapabilityExposureStatus.DOCUMENTED
    assert possible.evidence_status is CapabilityExposureStatus.TECHNICALLY_POSSIBLE


def test_shared_identifier_is_not_access_but_legal_gateway_evidence_is():
    with pytest.raises(ValueError):
        create_access_edge(source_ref="service:a",target_ref="service:b",access_type=InstitutionalAccessType.SHARES_WITH,
            assertion_id=uuid4(),epistemic_state=GraphEpistemicState.CURRENTLY_OBSERVED,identifier_overlap_only=True)
    gateway=create_access_edge(source_ref="Authority:ico",target_ref="Dataset:logs",
        access_type=InstitutionalAccessType.HAS_LEGAL_GATEWAY_TO,assertion_id=uuid4(),
        epistemic_state=GraphEpistemicState.CURRENTLY_OBSERVED,
        legal_instrument="statutory written-notice power",requirements=("threshold",))
    assert gateway.legal_instrument and gateway.requirements


def test_targeted_hypotheses_can_diverge_after_new_responses():
    profile,run,evidence=uuid4(),uuid4(),uuid4()
    first=detect_hypothesis(profile_id=profile,analysis_run_id=run,gap=EvidenceGap("undefined_internal_identifier","opaque-a","c",(evidence,)))
    second=detect_hypothesis(profile_id=profile,analysis_run_id=run,gap=EvidenceGap("unknown_linkage_mechanism","opaque-b","c",(evidence,)))
    confirmed=resolve_with_evidence(first,outcome=ResolutionOutcome.CONFIRMED,evidence_assertion_ids=(uuid4(),))
    unresolved=resolve_with_evidence(second,outcome=ResolutionOutcome.UNRESOLVED,evidence_assertion_ids=())
    assert confirmed.status.value=="confirmed" and unresolved.status.value=="unresolved"
    assert first.unresolved_question.endswith("?") and second.unresolved_question.endswith("?")


def test_deletion_observation_preserves_export_versus_legal_distinction():
    snapshot,node=uuid4(),uuid4()
    cut=IdentifierRemovalSimulation(id=uuid4(),linkability_snapshot_id=snapshot,graph_version="g1",
        selected_identifier_node_ids=(node,),calculation_method="exact",connected_components_before=1,
        connected_components_after=2,cross_domain_paths_before=3,cross_domain_paths_after=0,
        disconnected_path_fraction=1,calculated_at=datetime.now(timezone.utc))
    expected=build_deletion_simulation(profile_id=uuid4(),graph_snapshot_id=snapshot,graph_cut=cut,
        impacts=DeletionImpactInputs()).expected_removals[0]
    still=verify_later_export(expected,later_export_snapshot_id=uuid4(),observation=LaterExportObservation.PRESENT,
                              observed_assertion_ids=(uuid4(),))
    absent=verify_later_export(expected,later_export_snapshot_id=uuid4(),observation=LaterExportObservation.ABSENT)
    assert still.status is DeletionVerificationStatus.STILL_OBSERVED
    assert absent.status is DeletionVerificationStatus.CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT
    assert "not proof of legal deletion" in absent.explanation


def test_every_evidence_bearing_narrative_result_requires_resolvable_citations():
    with pytest.raises(ValueError,match="citations"):
        PrivacyQueryResult(tool="get_current_profile",data={"items":[{"claim":"x"}]},citations=(),evidence_bearing=True)
