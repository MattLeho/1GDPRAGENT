from datetime import datetime, timezone
from uuid import uuid4

import pytest

from intelligence.privacy.contracts import DeletionVerificationStatus, IdentifierRemovalSimulation
from intelligence.privacy.deletion import (
    DeletionImpactInputs,
    LaterExportObservation,
    build_deletion_simulation,
    expected_removal_baseline,
    verify_later_export,
)


def cut(snapshot_id):
    return IdentifierRemovalSimulation(
        id=uuid4(), linkability_snapshot_id=snapshot_id, graph_version="g1",
        selected_identifier_node_ids=(uuid4(),), calculation_method="exact",
        connected_components_before=1, connected_components_after=2,
        cross_domain_paths_before=4, cross_domain_paths_after=1,
        disconnected_path_fraction=.75, calculated_at=datetime.now(timezone.utc),
    )


def test_simulation_covers_all_required_effect_groups():
    snapshot = uuid4()
    value = build_deletion_simulation(
        profile_id=uuid4(), graph_snapshot_id=snapshot, graph_cut=cut(snapshot),
        impacts=DeletionImpactInputs(
            account_controller_links=("account:controller",), data_domain_paths=("health->ads",),
            capability_candidate_refs=("cross_service_identity_resolution",),
            linkability_indicator_refs=("stable-id-reuse",), evidence_assertion_ids=(uuid4(),),
        ),
    )
    assert {item.object_type for item in value.expected_removals} == {
        "identifier", "account_controller_link", "data_domain_path",
        "capability_candidate", "linkability_indicator",
    }
    assert value.predicted_effects["cross_domain_paths_after"] == 1


def test_graph_snapshot_mismatch_is_rejected():
    with pytest.raises(ValueError):
        build_deletion_simulation(profile_id=uuid4(), graph_snapshot_id=uuid4(),
                                  graph_cut=cut(uuid4()), impacts=DeletionImpactInputs())


def expected():
    snapshot = uuid4()
    return build_deletion_simulation(profile_id=uuid4(), graph_snapshot_id=snapshot,
                                     graph_cut=cut(snapshot), impacts=DeletionImpactInputs()).expected_removals[0]


def test_baseline_is_only_expected():
    result = expected_removal_baseline(expected(), later_export_snapshot_id=uuid4())
    assert result.status is DeletionVerificationStatus.EXPECTED_REMOVED


def test_absence_is_never_described_as_legal_deletion():
    result = verify_later_export(expected(), later_export_snapshot_id=uuid4(),
                                 observation=LaterExportObservation.ABSENT)
    assert result.status is DeletionVerificationStatus.CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT
    assert "not proof of legal deletion" in result.explanation


def test_present_requires_and_preserves_evidence():
    assertion = uuid4()
    result = verify_later_export(expected(), later_export_snapshot_id=uuid4(),
                                 observation=LaterExportObservation.PRESENT,
                                 observed_assertion_ids=(assertion,))
    assert result.status is DeletionVerificationStatus.STILL_OBSERVED
    assert result.observed_assertion_ids == (assertion,)
    with pytest.raises(ValueError):
        verify_later_export(expected(), later_export_snapshot_id=uuid4(),
                            observation=LaterExportObservation.PRESENT)


def test_incomparable_export_is_unverifiable():
    result = verify_later_export(expected(), later_export_snapshot_id=uuid4(),
                                 observation=LaterExportObservation.UNKNOWN)
    assert result.status is DeletionVerificationStatus.UNVERIFIABLE

