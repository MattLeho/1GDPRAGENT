"""Typed, profile-scoped, citation-bearing privacy query tools.

The registry is the complete model-facing surface.  Callers select one named
tool and structured arguments; neither SQL nor Cypher is accepted as input.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from db.postgres import PostgresClient, get_postgres_client
from .contracts import PrivacyQueryCitation, PrivacyQueryResult

PrivacyToolName = Literal[
    "get_current_profile", "get_profile_at", "compare_profile_periods",
    "trace_assertion", "get_assertion_evidence", "find_identifier_links",
    "get_identifier_centrality", "simulate_identifier_removal",
    "list_controller_assignments", "compare_behavioural_and_controller_profile",
    "list_capability_exposure", "trace_capability_evidence",
    "list_purpose_drift_candidates", "trace_purpose_lineage",
    "list_open_privacy_hypotheses", "compare_export_snapshots",
    "get_personal_drift", "get_controller_drift", "get_understanding_drift",
]

TOOL_NAMES: tuple[str, ...] = tuple(PrivacyToolName.__args__)


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AtArgs(EmptyArgs):
    as_of: datetime


class PeriodArgs(EmptyArgs):
    from_at: datetime
    to_at: datetime


class AssertionArgs(EmptyArgs):
    assertion_id: UUID


class IdentifierArgs(EmptyArgs):
    identifier_ref: str = Field(min_length=1, max_length=1000)


class IdentifierNodeArgs(EmptyArgs):
    identifier_node_id: UUID


class CapabilityArgs(EmptyArgs):
    capability_key: str = Field(min_length=1, max_length=200)


class PurposeArgs(EmptyArgs):
    purpose_id: UUID


class SnapshotPairArgs(EmptyArgs):
    before_snapshot_id: UUID
    after_snapshot_id: UUID


ARGUMENT_TYPES: dict[str, type[BaseModel]] = {
    "get_current_profile": EmptyArgs, "get_profile_at": AtArgs,
    "compare_profile_periods": PeriodArgs, "trace_assertion": AssertionArgs,
    "get_assertion_evidence": AssertionArgs, "find_identifier_links": IdentifierArgs,
    "get_identifier_centrality": IdentifierNodeArgs,
    "simulate_identifier_removal": IdentifierNodeArgs,
    "list_controller_assignments": EmptyArgs,
    "compare_behavioural_and_controller_profile": EmptyArgs,
    "list_capability_exposure": EmptyArgs, "trace_capability_evidence": CapabilityArgs,
    "list_purpose_drift_candidates": EmptyArgs, "trace_purpose_lineage": PurposeArgs,
    "list_open_privacy_hypotheses": EmptyArgs,
    "compare_export_snapshots": SnapshotPairArgs,
    "get_personal_drift": PeriodArgs, "get_controller_drift": PeriodArgs,
    "get_understanding_drift": PeriodArgs,
}


class PrivacyToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: PrivacyToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


_ASSERTION_SELECT = """
SELECT a.id,a.subject_type,a.subject_ref,a.predicate,a.object_type,a.object_ref,a.object_value,
       a.data_class,a.status,a.epistemic_basis,a.valid_from,a.valid_to,a.ingested_at,
       array_remove(array_agg(DISTINCT el.id),NULL) locator_ids,
       array_remove(array_agg(DISTINCT sa.id),NULL) artifact_ids
FROM assertions a
JOIN analysis_runs ar ON ar.id=a.analysis_run_id
LEFT JOIN assertion_evidence ae ON ae.assertion_id=a.id
LEFT JOIN evidence_locators el ON el.id=ae.evidence_locator_id
LEFT JOIN source_artifacts sa ON sa.id=el.artifact_id
WHERE ar.profile_id=$1
"""


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID): return str(value)
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, (list, tuple)): return [_jsonable(item) for item in value]
    if isinstance(value, dict): return {str(key): _jsonable(item) for key, item in value.items()}
    return value


class PrivacyQueryService:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def execute(self, *, profile_id: UUID, call: PrivacyToolCall) -> PrivacyQueryResult:
        args = ARGUMENT_TYPES[call.tool].model_validate(call.arguments)
        handler = getattr(self, f"_{call.tool}")
        rows, assertion_ids, unknowns = await handler(profile_id, args)
        citations = await self._citations(profile_id, assertion_ids)
        if rows and not citations:
            unknowns.append("Result has no resolvable Assertion/EvidenceLocator and is not evidence-bearing.")
        result = PrivacyQueryResult(
            tool=call.tool, data={"items": [_jsonable(dict(row)) for row in rows]},
            citations=tuple(citations), unknowns=tuple(unknowns), evidence_bearing=bool(citations),
        )
        await self._audit(profile_id, call, result)
        return result

    async def _assertions(self, profile_id: UUID, clause: str = "", *args: Any):
        query = _ASSERTION_SELECT + clause + """
 GROUP BY a.id,a.subject_type,a.subject_ref,a.predicate,a.object_type,a.object_ref,a.object_value,
          a.data_class,a.status,a.epistemic_basis,a.valid_from,a.valid_to,a.ingested_at
 ORDER BY a.ingested_at DESC,a.id LIMIT 500"""
        rows = await self.postgres.execute(query, profile_id, *args)
        return rows, {row["id"] for row in rows}, [] if rows else ["No matching accepted evidence was found."]

    async def _get_current_profile(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND (a.valid_from IS NULL OR a.valid_from<=NOW()) AND (a.valid_to IS NULL OR a.valid_to>NOW())")
    async def _get_profile_at(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND (a.valid_from IS NULL OR a.valid_from<=$2) AND (a.valid_to IS NULL OR a.valid_to>$2)", a.as_of)
    async def _compare_profile_periods(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND COALESCE(a.valid_from,a.ingested_at) BETWEEN $2 AND $3", a.from_at, a.to_at)
    async def _trace_assertion(self, p, a):
        return await self._assertions(p, " AND a.id=$2", a.assertion_id)
    async def _get_assertion_evidence(self, p, a):
        return await self._trace_assertion(p, a)
    async def _find_identifier_links(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND (a.subject_ref=$2 OR a.object_ref=$2 OR a.predicate ILIKE '%IDENTIFIER%')", a.identifier_ref)

    async def _get_identifier_centrality(self, p, a):
        rows = await self.postgres.execute("""SELECT s.* FROM identifier_statistics s JOIN privacy_graph_snapshots g
          ON g.id=s.graph_snapshot_id WHERE g.profile_id=$1 AND s.identifier_node_id=$2
          ORDER BY g.calculated_at DESC LIMIT 1""", p, a.identifier_node_id)
        ids = await self._snapshot_assertions(p, rows)
        return rows, ids, [] if rows else ["No centrality snapshot exists for this identifier."]
    async def _simulate_identifier_removal(self, p, a):
        rows = await self.postgres.execute("""SELECT r.* FROM identifier_removal_simulations r
          JOIN privacy_graph_snapshots g ON g.id=r.graph_snapshot_id
          WHERE g.profile_id=$1 AND $2=ANY(r.selected_identifier_node_ids)
          ORDER BY r.calculated_at DESC LIMIT 20""", p, a.identifier_node_id)
        ids = await self._snapshot_assertions(p, rows)
        return rows, ids, [] if rows else ["No stored exact graph-cut simulation exists for this identifier."]
    async def _snapshot_assertions(self, p, rows):
        if not rows: return set()
        snapshot_ids = [row["graph_snapshot_id"] for row in rows]
        values = await self.postgres.execute("SELECT unnest(edge_assertion_ids) id FROM privacy_graph_snapshots WHERE profile_id=$1 AND id=ANY($2::uuid[])", p, snapshot_ids)
        return {row["id"] for row in values}

    async def _list_controller_assignments(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND a.epistemic_basis='controller_assigned'")
    async def _compare_behavioural_and_controller_profile(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND (a.data_class='observed' OR a.epistemic_basis='controller_assigned')")

    async def _capabilities(self, p, key=None):
        clause = " AND c.capability_key=$2" if key else ""
        params = (p, key) if key else (p,)
        rows = await self.postgres.execute("""SELECT c.* FROM capability_candidates c WHERE c.profile_id=$1""" + clause + " ORDER BY c.calculated_at DESC LIMIT 200", *params)
        ids = {item for row in rows for item in (row["supporting_assertion_ids"] or [])}
        return rows, ids, [] if rows else ["No capability exposure candidates were found."]
    async def _list_capability_exposure(self, p, a): return await self._capabilities(p)
    async def _trace_capability_evidence(self, p, a): return await self._capabilities(p, a.capability_key)

    async def _list_purpose_drift_candidates(self, p, a):
        rows = await self.postgres.execute("""SELECT d.* FROM purpose_distance_assessments d
          JOIN analysis_runs ar ON ar.id=d.analysis_run_id WHERE ar.profile_id=$1 AND d.distance>=2
          ORDER BY d.created_at DESC LIMIT 200""", p)
        ids = {item for row in rows for item in (row["assertion_ids"] or [])}
        return rows, ids, [] if rows else ["No evidence-backed possible purpose drift candidates were found."]
    async def _trace_purpose_lineage(self, p, a):
        return await self._assertions(p, " AND a.status='accepted' AND a.predicate IN('ORIGINALLY_COLLECTED_FOR','CURRENTLY_USED_FOR','TECHNICALLY_ENABLES') AND (a.subject_ref=$2 OR a.object_ref=$2)", str(a.purpose_id))
    async def _list_open_privacy_hypotheses(self, p, a):
        rows = await self.postgres.execute("SELECT * FROM privacy_hypotheses WHERE profile_id=$1 AND status IN('open','request_drafted','request_sent','unresolved') ORDER BY updated_at DESC LIMIT 200", p)
        ids = {item for row in rows for item in (row["supporting_assertion_ids"] or [])}
        return rows, ids, [] if rows else ["No open privacy hypotheses were found."]
    async def _compare_export_snapshots(self, p, a):
        snaps = await self.postgres.execute("SELECT id,analysis_run_id,exported_at,controller_key FROM export_snapshots WHERE profile_id=$1 AND id IN($2,$3)", p, a.before_snapshot_id, a.after_snapshot_id)
        if len(snaps) != 2: return [], set(), ["Both export snapshots must exist in the authenticated profile."]
        run_ids = [row["analysis_run_id"] for row in snaps]
        return await self._assertions(p, " AND a.analysis_run_id=ANY($2::uuid[])", run_ids)

    async def _drift(self, p, a, kind):
        extra = {"personal":"", "controller":" AND a.epistemic_basis='controller_assigned'", "understanding":" AND a.data_class IN('derived','inferred')"}[kind]
        return await self._assertions(p, " AND COALESCE(a.valid_from,a.ingested_at) BETWEEN $2 AND $3" + extra, a.from_at, a.to_at)
    async def _get_personal_drift(self, p, a): return await self._drift(p, a, "personal")
    async def _get_controller_drift(self, p, a): return await self._drift(p, a, "controller")
    async def _get_understanding_drift(self, p, a): return await self._drift(p, a, "understanding")

    async def _citations(self, profile_id: UUID, assertion_ids: set[UUID]):
        if not assertion_ids: return []
        rows = await self.postgres.execute("""SELECT a.id assertion_id,el.id locator_id,sa.id artifact_id,
          CASE WHEN el.locator_type='text_span' THEN el.locator::text ELSE NULL END excerpt
          FROM assertions a JOIN analysis_runs ar ON ar.id=a.analysis_run_id
          JOIN assertion_evidence ae ON ae.assertion_id=a.id
          JOIN evidence_locators el ON el.id=ae.evidence_locator_id
          JOIN source_artifacts sa ON sa.id=el.artifact_id
          WHERE ar.profile_id=$1 AND a.id=ANY($2::uuid[]) ORDER BY a.id,el.id""", profile_id, list(assertion_ids))
        grouped: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(row["assertion_id"], {"locators": [], "artifacts": [], "excerpt": None})
            item["locators"].append(row["locator_id"]); item["artifacts"].append(row["artifact_id"])
            item["excerpt"] = item["excerpt"] or row["excerpt"]
        return [PrivacyQueryCitation(assertion_id=key,
                evidence_locator_ids=tuple(dict.fromkeys(value["locators"])),
                source_artifact_ids=tuple(dict.fromkeys(value["artifacts"])), excerpt=value["excerpt"])
                for key, value in grouped.items()]

    async def _audit(self, profile_id: UUID, call: PrivacyToolCall, result: PrivacyQueryResult):
        encoded = json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        await self.postgres.execute("""INSERT INTO privacy_query_audits(profile_id,tool_name,arguments,result_hash,
          assertion_ids,evidence_locator_ids,source_artifact_ids,unknowns) VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
          profile_id, call.tool, json.dumps(call.arguments, default=str), sha256(encoded.encode()).hexdigest(),
          [c.assertion_id for c in result.citations],
          [x for c in result.citations for x in c.evidence_locator_ids],
          [x for c in result.citations for x in c.source_artifact_ids], json.dumps(result.unknowns))
