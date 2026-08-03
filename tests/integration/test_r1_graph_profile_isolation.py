from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from graph.projection import GraphProjectionService


_LOCAL_ROOT = Path(__file__).resolve().parents[2]
ROOT = _LOCAL_ROOT if (_LOCAL_ROOT / "frontend").is_dir() else Path("/workspace")


class _Postgres:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *params: object):
        self.calls.append((query, params))
        return self.rows


class _Neo4j:
    def __init__(self):
        self.execute_calls: list[tuple[str, dict | None]] = []
        self.query_calls: list[tuple[str, dict | None]] = []

    async def execute(self, query: str, params: dict | None = None):
        self.execute_calls.append((query, params))
        return []

    async def query(self, query: str, params: dict | None = None):
        self.query_calls.append((query, params))
        return []


@pytest.mark.asyncio
async def test_foreign_and_missing_assertions_share_the_same_fail_closed_result():
    postgres = _Postgres()
    neo4j = _Neo4j()
    profile_id = uuid4()
    service = GraphProjectionService(postgres, neo4j)

    with pytest.raises(ValueError, match="only accepted, provenance-valid assertions"):
        await service.project_assertion(uuid4(), profile_id)

    ownership_query, params = postgres.calls[0]
    assert "ar.profile_id=$2::uuid" in ownership_query
    assert params[1] == str(profile_id)


@pytest.mark.asyncio
async def test_foreign_and_missing_nodes_cannot_be_retired_or_mutated_globally():
    postgres = _Postgres([{"allowed": 1}])
    neo4j = _Neo4j()
    profile_id = uuid4()
    service = GraphProjectionService(postgres, neo4j)

    with pytest.raises(ValueError, match="stable node_id was not found"):
        await service.retire_node(uuid4(), uuid4(), profile_id)

    mutation, params = neo4j.execute_calls[0]
    assert "owned.profile_id=$profile_id" in mutation
    assert "SET n." not in mutation
    assert params["profile_id"] == str(profile_id)


def test_graph_reads_and_api_mutations_are_explicitly_profile_scoped():
    stats = (ROOT / "frontend/app/api/graph/stats/route.ts").read_text(encoding="utf-8")
    dashboard = (ROOT / "frontend/lib/actions/dashboard.ts").read_text(encoding="utf-8")
    evidence = (ROOT / "intelligence/api/evidence.py").read_text(encoding="utf-8")
    projection = (ROOT / "intelligence/graph/projection.py").read_text(encoding="utf-8")

    assert stats.count("profile_id = $profileId") >= 3
    assert "MATCH (n:GraphNode)\n            WHERE" not in stats
    assert "getGraphNodeCount(profileId)" in dashboard
    assert "getGraphLinkCount(profileId)" in dashboard
    assert "MATCH (n) RETURN count(n)" not in dashboard
    assert evidence.count("require_profile_id(request)") >= 7
    assert "profile_id=profile_id" in evidence
    assert "apoc.refactor.mergeNodes" not in projection
    assert "SET n.retired" not in projection
    assert "owned.profile_id=$profile_id" in projection
