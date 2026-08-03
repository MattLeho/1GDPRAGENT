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
        "PolicyInstrument", "Claim", "SourceArtifact", "LegalBasis", "Dataset", "Authority",
        "CapabilityCandidate", "LinkabilitySnapshot", "IdentifierRemovalSimulation",
        "PurposeDistanceAssessment", "PrivacyHypothesis", "DeletionSimulation",
        "ExpectedRemoval", "DeletionVerification",
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

    async def project_assertion(self, assertion_id: UUID | str, profile_id: UUID | str) -> dict:
        await self.ensure_schema()
        rows=await self.postgres.execute(
            """SELECT a.*,ar.profile_id,COALESCE((SELECT array_agg(ae.evidence_locator_id ORDER BY ae.evidence_locator_id)
                 FROM assertion_evidence ae WHERE ae.assertion_id=a.id),'{}'::uuid[]) evidence_locator_ids
               ,COALESCE((SELECT array_agg(DISTINCT el.artifact_id ORDER BY el.artifact_id)
                 FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id
                 WHERE ae.assertion_id=a.id),'{}'::uuid[]) source_artifact_ids
               FROM assertions a JOIN analysis_runs ar ON ar.id=a.analysis_run_id
               WHERE a.id=$1::uuid AND ar.profile_id=$2::uuid AND a.status='accepted'
               AND NOT (a.epistemic_basis='model_hypothesis' AND NOT EXISTS(
                 SELECT 1 FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id
                 WHERE ae.assertion_id=a.id AND el.verified
                   AND el.verification_method IN ('exact_quote_match','structured_value_match','human_verified')))""",str(assertion_id),str(profile_id))
        if not rows: raise ValueError("only accepted, provenance-valid assertions can be projected")
        assertion=dict(rows[0])
        if assertion["profile_id"] is None:
            raise ValueError("projection requires an explicit canonical profile scope")
        subject_label=assert_personal_label(assertion["subject_type"])
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
        edge_epistemic=(
            "alleged_unverified" if str(assertion["epistemic_basis"])=="model_hypothesis"
            else "potentially_enabled" if assertion["predicate"].upper() in {"TECHNICALLY_COULD_ENABLE","CAN_REQUEST"}
            else "currently_observed"
        )
        cypher=f"""
        MERGE (s:GraphNode:{subject_label} {{node_id:$subject_id}})
        ON CREATE SET s.canonical_key=$subject_ref,s.created_at=datetime()
        MERGE (o:GraphNode:{object_label} {{node_id:$object_id}})
        ON CREATE SET o.canonical_key=$object_key,o.value=$object_value,o.source=$object_source,o.created_at=datetime()
        MERGE (s)-[r:{rel} {{assertion_id:$assertion_id}}]->(o)
        SET r.confidence=$confidence,r.epistemic_basis=$basis,r.data_class=$data_class,
            r.edge_epistemic=$edge_epistemic,r.assertion_status='accepted',
            r.valid_from=$valid_from,r.valid_to=$valid_to,
            r.controller_observed_from=$controller_observed_from,
            r.controller_observed_to=$controller_observed_to,
            r.exported_at=$exported_at,r.ingested_at=$ingested_at,
            r.system_asserted_at=$system_asserted_at,
            r.derivation_method=$derivation_method,r.derivation_version=$derivation_version,
            r.evidence_locator_ids=$evidence_locator_ids,r.source_artifact_ids=$source_artifact_ids,
            r.profile_id=$profile_id,r.projected_at=datetime()
        REMOVE r.inferred
        RETURN s.node_id AS subject_id,o.node_id AS object_id,r.assertion_id AS assertion_id
        """
        result=await self.neo4j.execute(cypher,{"subject_id":subject_id,"subject_ref":subject_ref,"object_id":object_id,"object_key":object_key,"object_value":object_ref,"assertion_id":str(assertion["id"]),"profile_id":str(assertion["profile_id"]),"confidence":float(assertion["confidence"]) if assertion["confidence"] is not None else None,"basis":str(assertion["epistemic_basis"]),"data_class":str(assertion["data_class"]),"object_source":"onsit" if is_onsit_label(object_label) else "gdpr","edge_epistemic":edge_epistemic,"valid_from":assertion["valid_from"].isoformat() if assertion["valid_from"] else None,"valid_to":assertion["valid_to"].isoformat() if assertion["valid_to"] else None,"controller_observed_from":assertion["controller_observed_from"].isoformat() if assertion["controller_observed_from"] else None,"controller_observed_to":assertion["controller_observed_to"].isoformat() if assertion["controller_observed_to"] else None,"exported_at":assertion["exported_at"].isoformat() if assertion["exported_at"] else None,"ingested_at":assertion["ingested_at"].isoformat() if assertion["ingested_at"] else None,"system_asserted_at":assertion["system_asserted_at"].isoformat() if assertion["system_asserted_at"] else None,"derivation_method":assertion["derivation_method"],"derivation_version":assertion["derivation_version"],"evidence_locator_ids":[str(value) for value in assertion["evidence_locator_ids"]],"source_artifact_ids":[str(value) for value in assertion["source_artifact_ids"]]})
        return result[0] if result else {"subject_id":subject_id,"object_id":object_id,"assertion_id":str(assertion["id"])}

    async def project_pending(self, limit: int=1000) -> int:
        rows=await self.postgres.execute("""SELECT a.id,ar.profile_id FROM assertions a JOIN analysis_runs ar ON ar.id=a.analysis_run_id
          WHERE a.status='accepted' AND ar.profile_id IS NOT NULL ORDER BY a.system_asserted_at LIMIT $1""",limit)
        for row in rows: await self.project_assertion(row["id"],row["profile_id"])
        return len(rows)

    async def retire_node(self, assertion_id: UUID | str, node_id: UUID | str, profile_id: UUID | str) -> None:
        await self._require_human_assertion(assertion_id,profile_id)
        result=await self.neo4j.execute(
            """MATCH (n:GraphNode {node_id:$node_id})-[owned]-(:GraphNode)
               WHERE owned.profile_id=$profile_id
               SET owned.profile_retired=true,
                   owned.profile_retired_by_assertion=$assertion_id,
                   owned.profile_retired_at=datetime()
               RETURN n.node_id AS node_id""",
            {"node_id":str(node_id),"assertion_id":str(assertion_id),"profile_id":str(profile_id)})
        if not result: raise ValueError("stable node_id was not found")

    async def merge_nodes(self, assertion_id: UUID | str, source_node_id: UUID | str, target_node_id: UUID | str, profile_id: UUID | str) -> None:
        await self._require_human_assertion(assertion_id,profile_id)
        if str(source_node_id)==str(target_node_id): raise ValueError("source and target must differ")
        nodes=await self.neo4j.query(
            """MATCH (source:GraphNode {node_id:$source_id})-[source_owned]-(:GraphNode),
                     (target:GraphNode {node_id:$target_id})-[target_owned]-(:GraphNode)
               WHERE source_owned.profile_id=$profile_id AND target_owned.profile_id=$profile_id
               RETURN [x IN labels(source) WHERE x<>'GraphNode'] AS source_labels,
                      [x IN labels(target) WHERE x<>'GraphNode'] AS target_labels
               LIMIT 1""",
            {"source_id":str(source_node_id),"target_id":str(target_node_id),"profile_id":str(profile_id)})
        if not nodes: raise ValueError("one or both stable node IDs were not found")
        if set(nodes[0]["source_labels"]) != set(nodes[0]["target_labels"]):
            raise ValueError("nodes from different ontology types cannot be merged")
        result=await self.neo4j.execute(
            """MATCH (source:GraphNode {node_id:$source_id})-[owned]-(:GraphNode)
               WHERE owned.profile_id=$profile_id
               SET owned.profile_retired=true,
                   owned.profile_merged_into_node_id=$target_id,
                   owned.profile_merged_by_assertion=$assertion_id,
                   owned.profile_merged_at=datetime()
               WITH DISTINCT source
               MATCH (target:GraphNode {node_id:$target_id})
               MERGE (source)-[marker:PROFILE_MERGED_INTO {profile_id:$profile_id}]->(target)
               SET marker.assertion_id=$assertion_id,marker.profile_layer_event=true,
                   marker.profile_retired=true,marker.created_at=datetime()
               RETURN target.node_id AS node_id""",
            {"source_id":str(source_node_id),"target_id":str(target_node_id),"assertion_id":str(assertion_id),"profile_id":str(profile_id)})
        if not result: raise ValueError("one or both stable node IDs were not found")

    async def mutate_onsit(self, assertion_id: UUID | str, action: str, node_ids: list[UUID], payload: dict, profile_id: UUID | str) -> int:
        await self._require_human_assertion(assertion_id,profile_id)
        params={"ids":[str(item) for item in node_ids],"assertion_id":str(assertion_id),"profile_id":str(profile_id),"risk":payload.get("riskLevel"),"tag":payload.get("tag")}
        if action=="delete": update="SET owned.profile_retired=true,owned.profile_retired_by_assertion=$assertion_id,owned.profile_retired_at=datetime()"
        elif action=="updateRisk" and params["risk"] in {"low","medium","high","critical"}: update="SET owned.risk_level=$risk,owned.updated_at=datetime(),owned.updated_by_assertion=$assertion_id"
        elif action=="addTag" and params["tag"]: update="SET owned.tags=CASE WHEN owned.tags IS NULL THEN [$tag] WHEN NOT $tag IN owned.tags THEN owned.tags+$tag ELSE owned.tags END,owned.updated_by_assertion=$assertion_id"
        elif action=="removeTag" and params["tag"]: update="SET owned.tags=[t IN coalesce(owned.tags,[]) WHERE t<>$tag],owned.updated_by_assertion=$assertion_id"
        else: raise ValueError("invalid ONSIT bulk action or payload")
        rows=await self.neo4j.execute(f"MATCH (n:GraphNode)-[owned]-(:GraphNode) WHERE n.node_id IN $ids AND n.source='onsit' AND owned.profile_id=$profile_id {update} RETURN count(DISTINCT n) AS affected",params)
        return int(rows[0]["affected"]) if rows else 0

    async def _require_human_assertion(self, assertion_id: UUID | str, profile_id: UUID | str) -> None:
        rows=await self.postgres.execute(
            """SELECT 1 FROM assertions a JOIN analysis_runs ar ON ar.id=a.analysis_run_id
               WHERE a.id=$1::uuid AND ar.profile_id=$2::uuid
                 AND a.status='accepted' AND a.epistemic_basis='human_confirmed'""",
            str(assertion_id),str(profile_id))
        if not rows: raise ValueError("graph mutation requires an accepted human-confirmed assertion")

    @staticmethod
    def _object_label(ref: str) -> str:
        label=ref.split(":",1)[0]
        return assert_graph_label(label)
