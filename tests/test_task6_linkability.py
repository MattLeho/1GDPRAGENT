from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from privacy.contracts import EdgeRisk, GraphEpistemicState
from privacy.linkability import (
    LinkabilityEdge,
    LinkabilityEngine,
    LinkabilityNode,
    LinkabilityRepository,
    reproducible_snapshot_hash,
)


PROFILE = UUID("00000000-0000-0000-0000-000000000099")
DOMAIN_A = UUID("00000000-0000-0000-0000-000000000001")
IDENTIFIER = UUID("00000000-0000-0000-0000-000000000002")
DOMAIN_B = UUID("00000000-0000-0000-0000-000000000003")
ASSERTION_A = UUID("00000000-0000-0000-0000-000000000011")
ASSERTION_B = UUID("00000000-0000-0000-0000-000000000012")
START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def risk(linkage_type="stable_identifier"):
    return EdgeRisk(
        linkage_type=linkage_type, directness=1.0, stability=0.9,
        cross_context_reuse=0.8, uniqueness_gain=0.7,
        legal_accessibility=None, reversibility=0.2, confidence=0.95,
    )


def topology(*, reverse=False, include_possible=False):
    nodes = [
        LinkabilityNode(DOMAIN_A, "data_point", data_domains=("location",)),
        LinkabilityNode(
            IDENTIFIER, "identifier", True,
            controller_ids=("c1", "c1", "c2"), service_ids=("s1", "s2"),
            data_domains=("identity",), schemas=("email", "account"),
            first_seen=START, last_seen=START + timedelta(days=10), occurrence_count=8,
        ),
        LinkabilityNode(DOMAIN_B, "data_point", data_domains=("purchase",)),
    ]
    edges = [
        LinkabilityEdge(DOMAIN_A, IDENTIFIER, ASSERTION_A, risk()),
        LinkabilityEdge(IDENTIFIER, DOMAIN_B, ASSERTION_B, risk()),
    ]
    if include_possible:
        edges.append(LinkabilityEdge(
            DOMAIN_A, DOMAIN_B, uuid4(), risk("possible_access"),
            GraphEpistemicState.POTENTIALLY_ENABLED,
        ))
    if reverse:
        nodes.reverse()
        edges = [LinkabilityEdge(
            edge.target_node_id, edge.source_node_id, edge.assertion_id,
            edge.risk, edge.epistemic_state,
        ) for edge in reversed(edges)]
    return nodes, edges


def test_snapshot_hash_is_reproducible_across_input_and_edge_orientation():
    nodes, edges = topology()
    reversed_nodes, reversed_edges = topology(reverse=True)
    kwargs = dict(graph_version="graph-v1", method="exact", method_version="1")
    assert reproducible_snapshot_hash(nodes=nodes, edges=edges, **kwargs) == reproducible_snapshot_hash(
        nodes=reversed_nodes, edges=reversed_edges, **kwargs,
    )


def test_snapshot_hash_changes_when_evidence_vector_changes():
    nodes, edges = topology()
    changed = list(edges)
    changed[0] = LinkabilityEdge(DOMAIN_A, IDENTIFIER, ASSERTION_A, risk("cookie"))
    kwargs = dict(graph_version="graph-v1", method="exact", method_version="1", nodes=nodes)
    assert reproducible_snapshot_hash(edges=edges, **kwargs) != reproducible_snapshot_hash(edges=changed, **kwargs)


def test_identifier_statistics_and_exact_graph_metrics():
    nodes, edges = topology(include_possible=True)
    analysis = LinkabilityEngine().build_snapshot(
        profile_id=PROFILE, graph_version="graph-v1", nodes=nodes, edges=edges,
        calculated_at=START,
    )
    statistic = analysis.snapshot.identifier_statistics[0]
    assert statistic.controller_count == 2
    assert statistic.service_count == 2
    assert statistic.data_domain_count == 1
    assert statistic.schema_count == 2
    assert statistic.temporal_persistence_seconds == 10 * 24 * 60 * 60
    assert statistic.occurrence_count == 8
    assert statistic.degree == 2
    assert statistic.betweenness == pytest.approx(1.0)
    assert statistic.articulation_point is True
    assert len(analysis.edge_risks) == 2  # potentially enabled is not currently observed


def test_removal_simulation_calculates_cross_domain_path_effect():
    nodes, edges = topology()
    engine = LinkabilityEngine()
    analysis = engine.build_snapshot(
        profile_id=PROFILE, graph_version="graph-v1", nodes=nodes, edges=edges,
        calculated_at=START,
    )
    result = engine.simulate_identifier_removal(
        analysis, nodes=nodes, edges=edges,
        selected_identifier_node_ids=[IDENTIFIER], calculated_at=START,
    )
    assert result.connected_components_before == 1
    assert result.connected_components_after == 2
    assert result.cross_domain_paths_before == 3
    assert result.cross_domain_paths_after == 0
    assert result.disconnected_path_fraction == 1.0
    assert result.linkability_snapshot_id == analysis.snapshot.id
    assert "cross_domain_connected_pairs" in result.calculation_method


def test_removal_rejects_non_identifier_and_snapshot_drift():
    nodes, edges = topology()
    engine = LinkabilityEngine()
    analysis = engine.build_snapshot(profile_id=PROFILE, graph_version="v1", nodes=nodes, edges=edges)
    with pytest.raises(ValueError, match="identifier"):
        engine.simulate_identifier_removal(
            analysis, nodes=nodes, edges=edges, selected_identifier_node_ids=[DOMAIN_A],
        )
    changed_edges = list(edges)
    changed_edges.pop()
    with pytest.raises(ValueError, match="does not match"):
        engine.simulate_identifier_removal(
            analysis, nodes=nodes, edges=changed_edges,
            selected_identifier_node_ids=[IDENTIFIER],
        )


def test_zero_cross_domain_paths_has_defined_zero_fraction():
    nodes = [
        LinkabilityNode(DOMAIN_A, "data", data_domains=("same",)),
        LinkabilityNode(IDENTIFIER, "identifier", True),
    ]
    edges = [LinkabilityEdge(DOMAIN_A, IDENTIFIER, ASSERTION_A, risk())]
    engine = LinkabilityEngine()
    analysis = engine.build_snapshot(profile_id=PROFILE, graph_version="v1", nodes=nodes, edges=edges)
    result = engine.simulate_identifier_removal(
        analysis, nodes=nodes, edges=edges, selected_identifier_node_ids=[IDENTIFIER],
    )
    assert result.cross_domain_paths_before == 0
    assert result.disconnected_path_fraction == 0.0


class FakePostgres:
    def __init__(self):
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return []


@pytest.mark.asyncio
async def test_persistence_helpers_use_migration_028_tables():
    nodes, edges = topology()
    engine = LinkabilityEngine()
    analysis = engine.build_snapshot(profile_id=PROFILE, graph_version="v1", nodes=nodes, edges=edges)
    simulation = engine.simulate_identifier_removal(
        analysis, nodes=nodes, edges=edges, selected_identifier_node_ids=[IDENTIFIER],
    )
    postgres = FakePostgres()
    repository = LinkabilityRepository(postgres)  # type: ignore[arg-type]
    persisted_id = await repository.save_analysis(analysis)
    await repository.save_simulation(simulation)
    sql = "\n".join(call[0] for call in postgres.calls)
    assert "privacy_graph_snapshots" in sql
    assert "identifier_statistics" in sql
    assert "edge_risks" in sql
    assert "identifier_removal_simulations" in sql
    assert analysis.snapshot_hash in postgres.calls[0][1]
    assert persisted_id == analysis.snapshot.id


def test_module_has_no_universal_score_or_deletion_claim():
    source = __import__("inspect").getsource(__import__("privacy.linkability", fromlist=["*"]))
    assert "privacy_score" not in source
    assert "removes linked data elsewhere" not in source
