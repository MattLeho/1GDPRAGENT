"""Extraction persistence through the assertion ledger (never direct Neo4j writes)."""
from __future__ import annotations

from datetime import datetime,timezone
from typing import Optional
from uuid import UUID

from evidence.ledger import EvidenceLedger
from evidence.models import AssertionCreate,AssertionStatus,DataClass,EpistemicBasis
from .schemas import ExtractionResult,GroundedEntity,SPOTriple,TextChunk


class ExtractionStorage:
    def __init__(self,neo4j_client=None,qdrant_client=None,*,ledger:EvidenceLedger|None=None,analysis_run_id:UUID|None=None,evidence_locator_ids:tuple[UUID,...]=()):
        self.qdrant=qdrant_client; self.ledger=ledger; self.analysis_run_id=analysis_run_id; self.evidence_locator_ids=evidence_locator_ids

    def _require_ledger(self):
        if not self.ledger or not self.analysis_run_id: raise ValueError("analysis_run_id and EvidenceLedger are required; direct graph storage was removed")

    async def store_triples(self,triples:list[SPOTriple],source:str,batch_size:int=50)->int:
        self._require_ledger(); stored=0
        for triple in triples:
            source_ids=tuple(UUID(item) for item in triple.source_assertion_ids)
            assertion=AssertionCreate(subject_type="Claim",subject_ref=f"{source}:{triple.subject}",predicate=triple.predicate,object_type="literal",object_value={"subject":triple.subject,"object":triple.object},assertion_type="hypothesis",data_class=DataClass.INFERRED if triple.inferred else DataClass.DERIVED,status=AssertionStatus.CANDIDATE,epistemic_basis=EpistemicBasis.MODEL_HYPOTHESIS,confidence=triple.confidence,ingested_at=datetime.now(timezone.utc),derivation_method="extraction_pipeline",derivation_version="task1",analysis_run_id=self.analysis_run_id,evidence_locator_ids=self.evidence_locator_ids,source_assertion_ids=source_ids)
            await self.ledger.create_assertion(assertion); stored+=1
        return stored

    async def store_entities(self,entities:list[GroundedEntity],source:str,batch_size:int=50)->int:
        self._require_ledger(); stored=0
        for entity in entities:
            assertion=AssertionCreate(subject_type="SourceArtifact",subject_ref=source,predicate="DESCRIBES",object_type="literal",object_value={"text":entity.text,"entity_class":entity.entity_class.value,"attributes":entity.attributes},assertion_type="hypothesis",data_class=DataClass.DERIVED,status=AssertionStatus.CANDIDATE,epistemic_basis=EpistemicBasis.MODEL_HYPOTHESIS,confidence=entity.confidence,ingested_at=datetime.now(timezone.utc),derivation_method="grounded_extraction",derivation_version="task1",analysis_run_id=self.analysis_run_id,evidence_locator_ids=self.evidence_locator_ids)
            await self.ledger.create_assertion(assertion); stored+=1
        return stored

    async def store_result(self,result:ExtractionResult)->dict[str,int]:
        return {"triples_stored":await self.store_triples(result.triples,result.source_document),"entities_stored":await self.store_entities(result.grounded_entities,result.source_document)}

    async def store_chunks(self,chunks:list[TextChunk],embeddings:list[list[float]],source:str,collection:str="gdpr_chunks")->int:
        if not self.qdrant or not chunks or not embeddings:return 0
        if len(chunks)!=len(embeddings):raise ValueError("Chunks and embeddings must have same length")
        from qdrant_client.models import PointStruct
        points=[PointStruct(id=f"{source}_{chunk.chunk_index}",vector=embedding,payload={"text":chunk.text,"start_offset":chunk.start_offset,"end_offset":chunk.end_offset,"chunk_index":chunk.chunk_index,"source":source}) for chunk,embedding in zip(chunks,embeddings)]
        await self.qdrant.upsert(collection_name=collection,points=points);return len(points)

    async def search_similar(self,query_embedding:list[float],collection:str="gdpr_chunks",limit:int=10)->list[TextChunk]:
        if not self.qdrant:return []
        results=await self.qdrant.search(collection_name=collection,query_vector=query_embedding,limit=limit)
        return [TextChunk(text=item.payload.get("text",""),start_offset=item.payload.get("start_offset",0),end_offset=item.payload.get("end_offset",0),chunk_index=item.payload.get("chunk_index",0),word_count=len(item.payload.get("text","").split())) for item in results]


async def get_entity_relationships(neo4j_client,entity_name:str,limit:int=50)->list[dict]:
    return await neo4j_client.query("MATCH (e:GraphNode {canonical_key:$name})-[r]-(t:GraphNode) WHERE coalesce(r.epistemic_basis,'')<>'model_hypothesis' RETURN e.node_id AS subject_id,type(r) AS predicate,t.node_id AS object_id,r.confidence AS confidence LIMIT $limit",{"name":entity_name,"limit":limit})


async def get_graph_data(neo4j_client,source_filter:Optional[str]=None,limit:int=500)->dict:
    where="WHERE r.source=$source AND coalesce(r.epistemic_basis,'')<>'model_hypothesis'" if source_filter else "WHERE coalesce(r.epistemic_basis,'')<>'model_hypothesis'"
    rows=await neo4j_client.query(f"MATCH (s:GraphNode)-[r]->(t:GraphNode) {where} RETURN s.node_id AS source,type(r) AS relationship,t.node_id AS target,r.confidence AS confidence LIMIT $limit",{"source":source_filter,"limit":limit})
    nodes={};edges=[]
    for row in rows:
        nodes[row["source"]]={"id":row["source"]};nodes[row["target"]]={"id":row["target"]};edges.append(row)
    return {"nodes":list(nodes.values()),"edges":edges}
