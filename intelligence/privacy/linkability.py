"""Deterministic structural-linkability analysis for Task 6.

The module analyses an undirected, high-value topology.  It deliberately emits
an evidence vector and individual graph metrics; it does not calculate a
universal privacy score or make claims about deletion at another service.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client
from privacy.contracts import (
    EdgeRisk,
    GraphEpistemicState,
    IdentifierRemovalSimulation,
    IdentifierStatistic,
    LinkabilitySnapshot,
)


@dataclass(frozen=True)
class LinkabilityNode:
    """A high-value graph node and the contexts observed for it."""

    id: UUID
    node_type: str
    is_identifier: bool = False
    controller_ids: tuple[str, ...] = ()
    service_ids: tuple[str, ...] = ()
    data_domains: tuple[str, ...] = ()
    schemas: tuple[str, ...] = ()
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    occurrence_count: int = 0

    def __post_init__(self) -> None:
        if self.occurrence_count < 0:
            raise ValueError("occurrence_count must be non-negative")
        if self.first_seen and self.last_seen and self.last_seen < self.first_seen:
            raise ValueError("last_seen must not precede first_seen")


@dataclass(frozen=True)
class LinkabilityEdge:
    source_node_id: UUID
    target_node_id: UUID
    assertion_id: UUID
    risk: EdgeRisk
    epistemic_state: GraphEpistemicState = GraphEpistemicState.CURRENTLY_OBSERVED

    def __post_init__(self) -> None:
        if self.source_node_id == self.target_node_id:
            raise ValueError("self-links are not part of the high-value topology")


@dataclass(frozen=True)
class PersistableEdgeRisk:
    assertion_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    vector: EdgeRisk


@dataclass(frozen=True)
class LinkabilityAnalysis:
    snapshot: LinkabilitySnapshot
    snapshot_hash: str
    edge_risks: tuple[PersistableEdgeRisk, ...]


def _uuid_key(value: UUID) -> str:
    return str(value)


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _canonical_edge(edge: LinkabilityEdge) -> dict[str, object]:
    source, target = sorted((str(edge.source_node_id), str(edge.target_node_id)))
    return {
        "source": source,
        "target": target,
        "assertion_id": str(edge.assertion_id),
        "epistemic_state": edge.epistemic_state.value,
        "risk": edge.risk.model_dump(mode="json"),
    }


def reproducible_snapshot_hash(
    *, graph_version: str, method: str, method_version: str,
    nodes: Iterable[LinkabilityNode], edges: Iterable[LinkabilityEdge],
) -> str:
    """Hash all calculation-relevant graph inputs using canonical JSON."""

    node_rows = []
    for node in sorted(nodes, key=lambda item: _uuid_key(item.id)):
        node_rows.append({
            "id": str(node.id), "node_type": node.node_type,
            "is_identifier": node.is_identifier,
            "controller_ids": sorted(set(node.controller_ids)),
            "service_ids": sorted(set(node.service_ids)),
            "data_domains": sorted(set(node.data_domains)),
            "schemas": sorted(set(node.schemas)),
            "first_seen": _utc_iso(node.first_seen),
            "last_seen": _utc_iso(node.last_seen),
            "occurrence_count": node.occurrence_count,
        })
    edge_rows = sorted(
        (_canonical_edge(edge) for edge in edges),
        key=lambda row: (row["source"], row["target"], row["assertion_id"]),
    )
    payload = {
        "graph_version": graph_version, "method": method,
        "method_version": method_version, "nodes": node_rows, "edges": edge_rows,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _adjacency(node_ids: Iterable[UUID], edges: Iterable[LinkabilityEdge]) -> dict[UUID, set[UUID]]:
    adjacency = {node_id: set() for node_id in node_ids}
    for edge in edges:
        if edge.source_node_id not in adjacency or edge.target_node_id not in adjacency:
            raise ValueError("every edge endpoint must be present in nodes")
        adjacency[edge.source_node_id].add(edge.target_node_id)
        adjacency[edge.target_node_id].add(edge.source_node_id)
    return adjacency


def _component_count(adjacency: dict[UUID, set[UUID]]) -> int:
    unseen = set(adjacency)
    count = 0
    while unseen:
        count += 1
        start = min(unseen, key=_uuid_key)
        queue = [start]
        unseen.remove(start)
        while queue:
            current = queue.pop()
            for neighbour in adjacency[current]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    queue.append(neighbour)
    return count


def _betweenness(adjacency: dict[UUID, set[UUID]]) -> dict[UUID, float]:
    """Exact normalized Brandes betweenness for an undirected graph."""

    result = {node: 0.0 for node in adjacency}
    ordered = sorted(adjacency, key=_uuid_key)
    for source in ordered:
        stack: list[UUID] = []
        predecessors = {node: [] for node in ordered}
        paths = dict.fromkeys(ordered, 0.0)
        paths[source] = 1.0
        distance = dict.fromkeys(ordered, -1)
        distance[source] = 0
        queue: deque[UUID] = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbour in sorted(adjacency[vertex], key=_uuid_key):
                if distance[neighbour] < 0:
                    queue.append(neighbour)
                    distance[neighbour] = distance[vertex] + 1
                if distance[neighbour] == distance[vertex] + 1:
                    paths[neighbour] += paths[vertex]
                    predecessors[neighbour].append(vertex)
        dependency = dict.fromkeys(ordered, 0.0)
        while stack:
            child = stack.pop()
            for parent in predecessors[child]:
                dependency[parent] += (paths[parent] / paths[child]) * (1.0 + dependency[child])
            if child != source:
                result[child] += dependency[child]
    size = len(ordered)
    scale = 1.0 / ((size - 1) * (size - 2)) if size > 2 else 0.0
    return {node: value * scale for node, value in result.items()}


def _articulation_points(adjacency: dict[UUID, set[UUID]]) -> set[UUID]:
    """Tarjan articulation points with stable traversal order."""

    discovery: dict[UUID, int] = {}
    low: dict[UUID, int] = {}
    parent: dict[UUID, UUID | None] = {}
    points: set[UUID] = set()
    counter = 0

    def visit(node: UUID) -> None:
        nonlocal counter
        counter += 1
        discovery[node] = low[node] = counter
        children = 0
        for neighbour in sorted(adjacency[node], key=_uuid_key):
            if neighbour not in discovery:
                parent[neighbour] = node
                children += 1
                visit(neighbour)
                low[node] = min(low[node], low[neighbour])
                if parent[node] is None and children > 1:
                    points.add(node)
                if parent[node] is not None and low[neighbour] >= discovery[node]:
                    points.add(node)
            elif neighbour != parent[node]:
                low[node] = min(low[node], discovery[neighbour])

    for node in sorted(adjacency, key=_uuid_key):
        if node not in discovery:
            parent[node] = None
            visit(node)
    return points


def _reachable(adjacency: dict[UUID, set[UUID]], source: UUID, target: UUID) -> bool:
    if source == target:
        return True
    seen = {source}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour == target:
                return True
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return False


def _cross_domain_paths(nodes: dict[UUID, LinkabilityNode], adjacency: dict[UUID, set[UUID]]) -> int:
    """Count connected unordered node pairs having disjoint observed domains."""

    candidates = sorted(
        (node for node in nodes.values() if node.data_domains),
        key=lambda item: _uuid_key(item.id),
    )
    count = 0
    for index, left in enumerate(candidates):
        left_domains = set(left.data_domains)
        for right in candidates[index + 1:]:
            if left_domains.isdisjoint(right.data_domains) and _reachable(adjacency, left.id, right.id):
                count += 1
    return count


class LinkabilityEngine:
    METHOD = "exact_undirected_high_value_topology"
    METHOD_VERSION = "1.0.0"

    def build_snapshot(
        self, *, profile_id: UUID, graph_version: str,
        nodes: Iterable[LinkabilityNode], edges: Iterable[LinkabilityEdge],
        snapshot_id: UUID | None = None, calculated_at: datetime | None = None,
    ) -> LinkabilityAnalysis:
        nodes = tuple(nodes)
        observed_edges = tuple(
            edge for edge in edges
            if edge.epistemic_state is GraphEpistemicState.CURRENTLY_OBSERVED
        )
        by_id = {node.id: node for node in nodes}
        if len(by_id) != len(nodes):
            raise ValueError("node ids must be unique")
        adjacency = _adjacency(by_id, observed_edges)
        betweenness = _betweenness(adjacency)
        articulation = _articulation_points(adjacency)
        statistics = []
        for node in sorted(nodes, key=lambda item: _uuid_key(item.id)):
            if not node.is_identifier:
                continue
            persistence = 0.0
            if node.first_seen and node.last_seen:
                persistence = (node.last_seen - node.first_seen).total_seconds()
            statistics.append(IdentifierStatistic(
                identifier_node_id=node.id,
                controller_count=len(set(node.controller_ids)),
                service_count=len(set(node.service_ids)),
                data_domain_count=len(set(node.data_domains)),
                schema_count=len(set(node.schemas)), first_seen=node.first_seen,
                last_seen=node.last_seen, temporal_persistence_seconds=persistence,
                occurrence_count=node.occurrence_count, degree=float(len(adjacency[node.id])),
                betweenness=betweenness[node.id], articulation_point=node.id in articulation,
            ))
        digest = reproducible_snapshot_hash(
            graph_version=graph_version, method=self.METHOD, method_version=self.METHOD_VERSION,
            nodes=nodes, edges=observed_edges,
        )
        snapshot = LinkabilitySnapshot(
            id=snapshot_id or uuid4(), profile_id=profile_id, graph_version=graph_version,
            method=self.METHOD, method_version=self.METHOD_VERSION,
            node_ids=tuple(sorted(by_id, key=_uuid_key)),
            edge_assertion_ids=tuple(sorted({edge.assertion_id for edge in observed_edges}, key=_uuid_key)),
            identifier_statistics=tuple(statistics),
            calculated_at=calculated_at or datetime.now(timezone.utc),
        )
        risks = tuple(PersistableEdgeRisk(
            assertion_id=edge.assertion_id,
            source_node_id=min((edge.source_node_id, edge.target_node_id), key=_uuid_key),
            target_node_id=max((edge.source_node_id, edge.target_node_id), key=_uuid_key),
            vector=edge.risk,
        ) for edge in sorted(observed_edges, key=lambda item: (
            min(_uuid_key(item.source_node_id), _uuid_key(item.target_node_id)),
            max(_uuid_key(item.source_node_id), _uuid_key(item.target_node_id)),
            _uuid_key(item.assertion_id),
        )))
        return LinkabilityAnalysis(snapshot=snapshot, snapshot_hash=digest, edge_risks=risks)

    def simulate_identifier_removal(
        self, analysis: LinkabilityAnalysis, *, nodes: Iterable[LinkabilityNode],
        edges: Iterable[LinkabilityEdge], selected_identifier_node_ids: Iterable[UUID],
        simulation_id: UUID | None = None, calculated_at: datetime | None = None,
    ) -> IdentifierRemovalSimulation:
        nodes = tuple(nodes)
        by_id = {node.id: node for node in nodes}
        selected = tuple(sorted(set(selected_identifier_node_ids), key=_uuid_key))
        if not selected:
            raise ValueError("at least one identifier must be selected")
        if any(node_id not in by_id or not by_id[node_id].is_identifier for node_id in selected):
            raise ValueError("selected nodes must be identifier nodes in the snapshot")
        if set(by_id) != set(analysis.snapshot.node_ids):
            raise ValueError("simulation nodes do not match the named graph snapshot")
        observed = tuple(edge for edge in edges if edge.epistemic_state is GraphEpistemicState.CURRENTLY_OBSERVED)
        expected_hash = reproducible_snapshot_hash(
            graph_version=analysis.snapshot.graph_version, method=analysis.snapshot.method,
            method_version=analysis.snapshot.method_version, nodes=nodes, edges=observed,
        )
        if expected_hash != analysis.snapshot_hash:
            raise ValueError("simulation topology does not match the named graph snapshot")
        before = _adjacency(by_id, observed)
        retained = {node_id: node for node_id, node in by_id.items() if node_id not in selected}
        after_edges = tuple(edge for edge in observed if edge.source_node_id in retained and edge.target_node_id in retained)
        after = _adjacency(retained, after_edges)
        before_paths = _cross_domain_paths(by_id, before)
        after_paths = _cross_domain_paths(retained, after)
        fraction = (before_paths - after_paths) / before_paths if before_paths else 0.0
        return IdentifierRemovalSimulation(
            id=simulation_id or uuid4(), linkability_snapshot_id=analysis.snapshot.id,
            graph_version=analysis.snapshot.graph_version,
            selected_identifier_node_ids=selected,
            calculation_method=f"{self.METHOD}@{self.METHOD_VERSION}:cross_domain_connected_pairs",
            connected_components_before=_component_count(before),
            connected_components_after=_component_count(after),
            cross_domain_paths_before=before_paths, cross_domain_paths_after=after_paths,
            disconnected_path_fraction=fraction,
            calculated_at=calculated_at or datetime.now(timezone.utc),
        )


class LinkabilityRepository:
    """Persistence helpers constrained to migration 028 and PostgresClient."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def save_analysis(self, analysis: LinkabilityAnalysis) -> UUID:
        snapshot = analysis.snapshot
        records = await self.postgres.execute(
            """INSERT INTO privacy_graph_snapshots
               (id,profile_id,graph_version,method,method_version,node_ids,edge_assertion_ids,snapshot_hash,calculated_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
               ON CONFLICT (profile_id,graph_version,snapshot_hash) DO NOTHING RETURNING id""",
            snapshot.id, snapshot.profile_id, snapshot.graph_version, snapshot.method,
            snapshot.method_version, list(snapshot.node_ids), list(snapshot.edge_assertion_ids),
            analysis.snapshot_hash, snapshot.calculated_at,
        )
        if records:
            persisted_snapshot_id=records[0]["id"]
        else:
            existing=await self.postgres.execute(
                "SELECT id FROM privacy_graph_snapshots WHERE profile_id=$1 AND graph_version=$2 AND snapshot_hash=$3",
                snapshot.profile_id,snapshot.graph_version,analysis.snapshot_hash,
            )
            persisted_snapshot_id=existing[0]["id"] if existing else snapshot.id
        for statistic in snapshot.identifier_statistics:
            await self.postgres.execute(
                """INSERT INTO identifier_statistics
                   (graph_snapshot_id,identifier_node_id,controller_count,service_count,data_domain_count,
                    schema_count,first_seen,last_seen,temporal_persistence_seconds,occurrence_count,degree,
                    betweenness,articulation_point)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                   ON CONFLICT (graph_snapshot_id,identifier_node_id) DO NOTHING""",
                persisted_snapshot_id, statistic.identifier_node_id, statistic.controller_count,
                statistic.service_count, statistic.data_domain_count, statistic.schema_count,
                statistic.first_seen, statistic.last_seen, statistic.temporal_persistence_seconds,
                statistic.occurrence_count, statistic.degree, statistic.betweenness,
                statistic.articulation_point,
            )
        for edge in analysis.edge_risks:
            vector = edge.vector
            await self.postgres.execute(
                """INSERT INTO edge_risks
                   (graph_snapshot_id,assertion_id,source_node_id,target_node_id,linkage_type,directness,
                    stability,cross_context_reuse,uniqueness_gain,legal_accessibility,reversibility,confidence)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                   ON CONFLICT (graph_snapshot_id,source_node_id,target_node_id,linkage_type) DO NOTHING""",
                persisted_snapshot_id, edge.assertion_id, edge.source_node_id, edge.target_node_id,
                vector.linkage_type, vector.directness, vector.stability,
                vector.cross_context_reuse, vector.uniqueness_gain,
                vector.legal_accessibility, vector.reversibility, vector.confidence,
            )
        return persisted_snapshot_id

    async def save_simulation(self, simulation: IdentifierRemovalSimulation) -> None:
        await self.postgres.execute(
            """INSERT INTO identifier_removal_simulations
               (id,graph_snapshot_id,graph_version,selected_identifier_node_ids,calculation_method,
                connected_components_before,connected_components_after,cross_domain_paths_before,
                cross_domain_paths_after,disconnected_path_fraction,calculated_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT (id) DO NOTHING""",
            simulation.id, simulation.linkability_snapshot_id, simulation.graph_version,
            list(simulation.selected_identifier_node_ids), simulation.calculation_method,
            simulation.connected_components_before, simulation.connected_components_after,
            simulation.cross_domain_paths_before, simulation.cross_domain_paths_after,
            simulation.disconnected_path_fraction, simulation.calculated_at,
        )
