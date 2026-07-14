"""Graph-cut deletion expectations and observation-limited verification.

This module predicts what a scoped deletion plan should remove.  Its verifier
only compares later observed exports; it never claims that absence proves
legal or backend deletion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from uuid import NAMESPACE_URL, UUID, uuid5

from db.postgres import PostgresClient, get_postgres_client
from .contracts import (
    DeletionSimulation,
    DeletionVerification,
    DeletionVerificationStatus,
    ExpectedRemoval,
    IdentifierRemovalSimulation,
)

METHOD = "observed_graph_cut_expected_removal"
METHOD_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class DeletionImpactInputs:
    """Evidence-backed objects downstream of the selected identifiers."""

    account_controller_links: tuple[str, ...] = ()
    data_domain_paths: tuple[str, ...] = ()
    capability_candidate_refs: tuple[str, ...] = ()
    linkability_indicator_refs: tuple[str, ...] = ()
    evidence_assertion_ids: tuple[UUID, ...] = ()


class LaterExportObservation(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


def _expected(
    simulation_id: UUID,
    object_type: str,
    object_ref: str,
    effect: str,
    assertion_ids: tuple[UUID, ...],
) -> ExpectedRemoval:
    stable = f"{simulation_id}:{object_type}:{object_ref}"
    return ExpectedRemoval(
        id=uuid5(NAMESPACE_URL, stable),
        deletion_simulation_id=simulation_id,
        object_type=object_type,
        object_ref=object_ref,
        expected_effect=effect,
        evidence_assertion_ids=tuple(sorted(set(assertion_ids), key=str)),
    )


def build_deletion_simulation(
    *,
    profile_id: UUID,
    graph_snapshot_id: UUID,
    graph_cut: IdentifierRemovalSimulation,
    impacts: DeletionImpactInputs,
    deletion_plan_id: UUID | None = None,
    simulation_id: UUID | None = None,
    calculated_at: datetime | None = None,
) -> DeletionSimulation:
    """Translate an exact identifier graph cut into auditable expectations."""

    if graph_cut.linkability_snapshot_id != graph_snapshot_id:
        raise ValueError("graph cut and deletion simulation must name the same snapshot")
    stable = f"{profile_id}:{graph_snapshot_id}:{deletion_plan_id}:{graph_cut.id}:{METHOD_VERSION}"
    identifier = simulation_id or uuid5(NAMESPACE_URL, stable)
    assertions = impacts.evidence_assertion_ids
    removals: list[ExpectedRemoval] = []
    for node_id in graph_cut.selected_identifier_node_ids:
        removals.append(_expected(identifier, "identifier", str(node_id), "expected absent from a comparable later export", assertions))
    groups = (
        ("account_controller_link", impacts.account_controller_links, "expected observed link to be removed"),
        ("data_domain_path", impacts.data_domain_paths, "expected observed path to be disconnected"),
        ("capability_candidate", impacts.capability_candidate_refs, "expected supporting basis to be reduced or removed"),
        ("linkability_indicator", impacts.linkability_indicator_refs, "expected observed indicator to be reduced or removed"),
    )
    for object_type, refs, effect in groups:
        for ref in sorted(set(refs)):
            removals.append(_expected(identifier, object_type, ref, effect, assertions))
    predicted = {
        "connected_components_before": graph_cut.connected_components_before,
        "connected_components_after": graph_cut.connected_components_after,
        "cross_domain_paths_before": graph_cut.cross_domain_paths_before,
        "cross_domain_paths_after": graph_cut.cross_domain_paths_after,
        "disconnected_path_fraction": graph_cut.disconnected_path_fraction,
        "scope_note": "Prediction is limited to the named observed graph snapshot and deletion plan.",
    }
    return DeletionSimulation(
        id=identifier,
        profile_id=profile_id,
        graph_snapshot_id=graph_snapshot_id,
        method=METHOD,
        method_version=METHOD_VERSION,
        deletion_plan_id=deletion_plan_id,
        selected_identifier_node_ids=graph_cut.selected_identifier_node_ids,
        predicted_effects=predicted,
        expected_removals=tuple(removals),
        calculated_at=calculated_at or datetime.now(timezone.utc),
    )


def expected_removal_baseline(
    expected: ExpectedRemoval, *, later_export_snapshot_id: UUID, checked_at: datetime | None = None
) -> DeletionVerification:
    return _verification(
        expected,
        later_export_snapshot_id,
        DeletionVerificationStatus.EXPECTED_REMOVED,
        (),
        "Removal is predicted by the named simulation but has not yet been checked against a later export.",
        checked_at,
    )


def verify_later_export(
    expected: ExpectedRemoval,
    *,
    later_export_snapshot_id: UUID,
    observation: LaterExportObservation,
    observed_assertion_ids: tuple[UUID, ...] = (),
    checked_at: datetime | None = None,
) -> DeletionVerification:
    if observation is LaterExportObservation.PRESENT:
        if not observed_assertion_ids:
            raise ValueError("a present observation requires assertion evidence")
        status = DeletionVerificationStatus.STILL_OBSERVED
        explanation = "The expected object is still observed in the named later export."
    elif observation is LaterExportObservation.ABSENT:
        if observed_assertion_ids:
            raise ValueError("absence cannot carry assertions claiming the object was observed")
        status = DeletionVerificationStatus.CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT
        explanation = (
            "The object was not found in the named comparable later export. "
            "This confirms export absence only; it is not proof of legal deletion or deletion from every controller system."
        )
    else:
        status = DeletionVerificationStatus.UNVERIFIABLE
        explanation = "The later export is missing, incomparable, incomplete, or otherwise insufficient to verify the expectation."
    return _verification(expected, later_export_snapshot_id, status, observed_assertion_ids, explanation, checked_at)


def _verification(
    expected: ExpectedRemoval,
    snapshot_id: UUID,
    status: DeletionVerificationStatus,
    assertions: tuple[UUID, ...],
    explanation: str,
    checked_at: datetime | None,
) -> DeletionVerification:
    identifier = uuid5(NAMESPACE_URL, f"{expected.id}:{snapshot_id}:{status.value}")
    return DeletionVerification(
        id=identifier,
        expected_removal_id=expected.id,
        later_export_snapshot_id=snapshot_id,
        status=status,
        observed_assertion_ids=tuple(sorted(set(assertions), key=str)),
        checked_at=checked_at or datetime.now(timezone.utc),
        explanation=explanation,
    )


class DeletionAnalysisRepository:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def save_simulation(self, value: DeletionSimulation) -> None:
        await self.postgres.execute(
            """INSERT INTO deletion_simulations(id,profile_id,deletion_plan_id,graph_snapshot_id,method,
               method_version,selected_identifier_node_ids,predicted_effects,calculated_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(id) DO NOTHING""",
            value.id, value.profile_id, value.deletion_plan_id, value.graph_snapshot_id,
            value.method, value.method_version, list(value.selected_identifier_node_ids),
            json.dumps(value.predicted_effects), value.calculated_at,
        )
        for removal in value.expected_removals:
            await self.postgres.execute(
                """INSERT INTO expected_removals(id,deletion_simulation_id,object_type,object_ref,
                   expected_effect,evidence_assertion_ids) VALUES($1,$2,$3,$4,$5,$6)
                   ON CONFLICT(deletion_simulation_id,object_type,object_ref) DO NOTHING""",
                removal.id, removal.deletion_simulation_id, removal.object_type, removal.object_ref,
                removal.expected_effect, list(removal.evidence_assertion_ids),
            )

    async def save_verification(self, value: DeletionVerification) -> None:
        await self.postgres.execute(
            """INSERT INTO deletion_verifications(id,expected_removal_id,later_export_snapshot_id,status,
               observed_assertion_ids,explanation,checked_at) VALUES($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT(expected_removal_id,later_export_snapshot_id) DO NOTHING""",
            value.id, value.expected_removal_id, value.later_export_snapshot_id,
            value.status.value, list(value.observed_assertion_ids), value.explanation, value.checked_at,
        )
