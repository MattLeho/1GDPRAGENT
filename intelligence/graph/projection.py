from __future__ import annotations

import json
from uuid import UUID

from db.neo4j import Neo4jClient, get_neo4j_client
from db.postgres import PostgresClient, get_postgres_client

from .ontology import assert_graph_label, assert_personal_label, is_onsit_label, relationship_type, stable_node_id


class GraphProjectionService:
    """The sole writer for the personal-data Neo4j projection."""

    HIGH_VALUE_LABELS = frozenset({
        "Subject", "ControllerProfile", "Organisation", "Account", "Identifier",
        "DataDomain", "Topic", "DataPoint", "TemporalState", "ProjectEpisode",
        "ProcessingActivity", "Purpose", "Capability", "CapabilityExposureState",
        "PolicyInstrument", "Claim", "SourceArtifact",
    })

    def __init__(self, postgres: PostgresClient | None=None, neo4j: Neo4jClient | None=None):
        self.postgres=postgres or get_postgres_client(); self.neo4j=neo4j or get_neo4j_client()

    async def ensure_schema(self) -> None:
        await self.neo4j.execute("CREATE CONSTRAINT graph_node_id IF NOT EXISTS FOR (n:GraphNode) REQUIRE n.node_id IS UNIQUE")
        await self.neo4j.execute("CREATE INDEX assertion_edge_id IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.assertion_id)")

    async def backfill_legacy_node_ids(self) -> int:
        await self.ensure_schema()
        rows=await self.neo4j.query("MATCH (n) WHERE n.node_id IS NULL RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS props")
        existing=await self.neo4j.query("MATCH (n:GraphNode) WHERE n.node_id IS NOT NULL RETURN n.node_id AS node_id")
        used={row["node_id"] for row in existing}
        updated=0
        for row in rows:
            labels=[label for label in row.get("labels",[]) if label!="GraphNode"]
            label=sorted(labels)[0] if labels else "LegacyNode"
            props=row.get("props") or {}
            identity=next((str(props[key]) for key in ("canonical_key","uid","id","address","number","username","domain","name","label","value") if props.get(key) not in (None,"")),row["element_id"])
            node_id=str(stable_node_id(label,f"legacy:{identity}"))
            if node_id in used:
                # Preserve distinct legacy occurrences; equivalence requires a
                # typed deterministic or human-approved resolver decision.
                node_id=str(stable_node_id(label,f"legacy:{identity}:{row['element_id']}"))
            await self.neo4j.execute("MATCH (n) WHERE elementId(n)=$element_id SET n:GraphNode,n.node_id=$node_id,n.legacy_backfilled=true",{"element_id":row["element_id"],"node_id":node_id})
            used.add(node_id)
            updated+=1
        return updated

    async def project_assertion(self, assertion_id: UUID | str) -> dict:
        await self.ensure_schema()
        rows=await self.postgres.execute(
            """SELECT a.* FROM assertions a WHERE a.id=$1::uuid AND a.status='accepted'
               AND NOT (a.epistemic_basis='model_hypothesis' AND NOT EXISTS(
                 SELECT 1 FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id
                 WHERE ae.assertion_id=a.id AND el.verified
                   AND el.verification_method IN ('exact_quote_match','structured_value_match','human_verified')))""",str(assertion_id))
        if not rows: raise ValueError("only accepted, provenance-valid assertions can be projected")
        assertion=dict(rows[0]); subject_label=assert_personal_label(assertion["subject_type"])
        if subject_label not in self.HIGH_VALUE_LABELS:
            raise ValueError("assertion subject is not part of the high-value privacy topology")
        subject_ref=assertion["subject_ref"]; subject_id=str(stable_node_id(subject_label,subject_ref))
        if assertion["object_ref"]:
            object_ref=assertion["object_ref"]
        else:
            value=assertion["object_value"]
            object_ref=json.dumps(value,sort_keys=True,separators=(",",":"),default=str)
        object_label="DataPoint" if assertion["object_type"]!="node_ref" else self._object_label(object_ref)
        if object_label not in self.HIGH_VALUE_LABELS:
            raise ValueError("assertion object is not part of the high-value privacy topology")
        if subject_label == "ControllerProfile" and object_label == "Subject":
            raise ValueError("controller-assigned profiles must not mutate Subject behavioural identity")
        object_key=object_ref.split(":",1)[-1] if assertion["object_type"]=="node_ref" and ":" in object_ref else object_ref
        object_id=str(stable_node_id(object_label,object_key)); rel=relationship_type(assertion["predicate"])
        cypher=f"""
        MERGE (s:GraphNode:{subject_label} {{node_id:$subject_id}})
        ON CREATE SET s.canonical_key=$subject_ref,s.created_at=datetime()
        MERGE (o:GraphNode:{object_label} {{node_id:$object_id}})
        ON CREATE SET o.canonical_key=$object_key,o.value=$object_value,o.source=$object_source,o.created_at=datetime()
        MERGE (s)-[r:{rel} {{assertion_id:$assertion_id}}]->(o)
        SET r.confidence=$confidence,r.epistemic_basis=$basis,r.data_class=$data_class,
            r.inferred=($basis='model_hypothesis'),r.projected_at=datetime()
        RETURN s.node_id AS subject_id,o.node_id AS object_id,r.assertion_id AS assertion_id
        """
        result=await self.neo4j.execute(cypher,{"subject_id":subject_id,"subject_ref":subject_ref,"object_id":object_id,"object_key":object_key,"object_value":object_ref,"assertion_id":str(assertion["id"]),"confidence":float(assertion["confidence"]) if assertion["confidence"] is not None else None,"basis":str(assertion["epistemic_basis"]),"data_class":str(assertion["data_class"]),"object_source":"onsit" if is_onsit_label(object_label) else "gdpr"})
        return result[0] if result else {"subject_id":subject_id,"object_id":object_id,"assertion_id":str(assertion["id"])}

    async def project_pending(self, limit: int=1000) -> int:
        rows=await self.postgres.execute("SELECT id FROM assertions WHERE status='accepted' ORDER BY system_asserted_at LIMIT $1",limit)
        for row in rows: await self.project_assertion(row["id"])
        return len(rows)

    async def retire_node(self, assertion_id: UUID | str, node_id: UUID | str) -> None:
        await self._require_human_assertion(assertion_id)
        result=await self.neo4j.execute("MATCH (n:GraphNode {node_id:$node_id}) SET n.retired=true,n.retired_by_assertion=$assertion_id,n.retired_at=datetime() RETURN n.node_id AS node_id",{"node_id":str(node_id),"assertion_id":str(assertion_id)})
        if not result: raise ValueError("stable node_id was not found")

    async def merge_nodes(self, assertion_id: UUID | str, source_node_id: UUID | str, target_node_id: UUID | str) -> None:
        await self._require_human_assertion(assertion_id)
        if str(source_node_id)==str(target_node_id): raise ValueError("source and target must differ")
        nodes=await self.neo4j.query("MATCH (source:GraphNode {node_id:$source_id}),(target:GraphNode {node_id:$target_id}) RETURN [x IN labels(source) WHERE x<>'GraphNode'] AS source_labels,[x IN labels(target) WHERE x<>'GraphNode'] AS target_labels",{"source_id":str(source_node_id),"target_id":str(target_node_id)})
        if not nodes: raise ValueError("one or both stable node IDs were not found")
        if set(nodes[0]["source_labels"]) != set(nodes[0]["target_labels"]):
            raise ValueError("nodes from different ontology types cannot be merged")
        result=await self.neo4j.execute(
            """MATCH (source:GraphNode {node_id:$source_id}),(target:GraphNode {node_id:$target_id})
               CALL apoc.refactor.mergeNodes([target,source],{properties:'discard',mergeRels:true}) YIELD node
               SET node.merged_by_assertion=$assertion_id,node.updated_at=datetime()
               RETURN node.node_id AS node_id""",
            {"source_id":str(source_node_id),"target_id":str(target_node_id),"assertion_id":str(assertion_id)})
        if not result: raise ValueError("one or both stable node IDs were not found")

    async def mutate_onsit(self, assertion_id: UUID | str, action: str, node_ids: list[UUID], payload: dict) -> int:
        await self._require_human_assertion(assertion_id)
        params={"ids":[str(item) for item in node_ids],"assertion_id":str(assertion_id),"risk":payload.get("riskLevel"),"tag":payload.get("tag")}
        if action=="delete": update="SET n.retired=true,n.retired_by_assertion=$assertion_id,n.retired_at=datetime()"
        elif action=="updateRisk" and params["risk"] in {"low","medium","high","critical"}: update="SET n.riskLevel=$risk,n.updatedAt=datetime(),n.updated_by_assertion=$assertion_id"
        elif action=="addTag" and params["tag"]: update="SET n.tags=CASE WHEN n.tags IS NULL THEN [$tag] WHEN NOT $tag IN n.tags THEN n.tags+$tag ELSE n.tags END,n.updated_by_assertion=$assertion_id"
        elif action=="removeTag" and params["tag"]: update="SET n.tags=[t IN coalesce(n.tags,[]) WHERE t<>$tag],n.updated_by_assertion=$assertion_id"
        else: raise ValueError("invalid ONSIT bulk action or payload")
        rows=await self.neo4j.execute(f"MATCH (n:GraphNode) WHERE n.node_id IN $ids AND n.source='onsit' {update} RETURN count(n) AS affected",params)
        return int(rows[0]["affected"]) if rows else 0

    async def _require_human_assertion(self, assertion_id: UUID | str) -> None:
        rows=await self.postgres.execute("SELECT 1 FROM assertions WHERE id=$1::uuid AND status='accepted' AND epistemic_basis='human_confirmed'",str(assertion_id))
        if not rows: raise ValueError("graph mutation requires an accepted human-confirmed assertion")

    @staticmethod
    def _object_label(ref: str) -> str:
        label=ref.split(":",1)[0]
        return assert_graph_label(label)
