"""
Storage Adapters for Extraction Results

Provides persistence layer for extracted knowledge:
- Neo4j: Store entities and relationships as graph
- Qdrant: Store embeddings for hybrid RAG (optional)

Key Features:
- MERGE-based upsert to prevent duplicates
- Batch operations for efficiency
- Inferred relationship marking
- Provenance metadata preservation
"""

from __future__ import annotations

import asyncio
from typing import Optional, Any
from datetime import datetime

from .schemas import SPOTriple, GroundedEntity, TextChunk, ExtractionResult


# =============================================================================
# Neo4j Storage
# =============================================================================

class ExtractionStorage:
    """
    Storage adapter for extraction results.
    
    Stores triples as Neo4j relationships and entities as nodes.
    Optionally stores chunks in Qdrant for vector search.
    
    Usage:
        storage = ExtractionStorage(neo4j_client)
        count = await storage.store_triples(triples, source="gdpr_doc.pdf")
    """
    
    def __init__(
        self,
        neo4j_client,  # Neo4jClient from db/neo4j.py
        qdrant_client=None,  # Optional QdrantClient
    ):
        """
        Initialize storage adapter.
        
        Args:
            neo4j_client: Neo4jClient instance
            qdrant_client: Optional QdrantClient for vector storage
        """
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
    
    async def store_triples(
        self,
        triples: list[SPOTriple],
        source: str,
        batch_size: int = 50,
    ) -> int:
        """
        Store SPO triples as Neo4j graph.
        
        Creates/merges entity nodes and relationship edges.
        
        Args:
            triples: List of SPOTriple objects
            source: Source document identifier
            batch_size: Triples per batch
            
        Returns:
            Number of relationships created/updated
        """
        if not triples:
            return 0
        
        stored = 0
        
        # Process in batches
        for i in range(0, len(triples), batch_size):
            batch = triples[i:i + batch_size]
            statements = []
            
            for triple in batch:
                # Build MERGE statement
                cypher = self._build_triple_cypher(triple, source)
                statements.append({"statement": cypher, "parameters": {}})
            
            try:
                await self.neo4j.execute_batch(statements)
                stored += len(batch)
            except Exception:
                # Continue on error, log at higher level
                continue
        
        return stored
    
    def _build_triple_cypher(
        self,
        triple: SPOTriple,
        source: str,
    ) -> str:
        """
        Build Cypher MERGE statement for a triple.
        
        Creates subject and object nodes, then relationship.
        """
        # Sanitize strings for Cypher
        subj = self._sanitize(triple.subject)
        obj = self._sanitize(triple.object)
        pred = triple.predicate.replace(" ", "_").upper()
        
        # Build relationship properties
        rel_props = {
            "confidence": triple.confidence,
            "inferred": triple.inferred,
            "source": source,
            "extracted_at": datetime.utcnow().isoformat(),
        }
        
        if triple.source_chunk is not None:
            rel_props["source_chunk"] = triple.source_chunk
        
        rel_props_str = ", ".join(
            f"{k}: {self._cypher_value(v)}"
            for k, v in rel_props.items()
        )
        
        return f"""
        MERGE (s:Entity {{name: '{subj}'}})
        ON CREATE SET s.created_at = datetime()
        MERGE (o:Entity {{name: '{obj}'}})
        ON CREATE SET o.created_at = datetime()
        MERGE (s)-[r:{pred}]->(o)
        ON CREATE SET {', '.join(f'r.{k} = {self._cypher_value(v)}' for k, v in rel_props.items())}
        ON MATCH SET r.updated_at = datetime(), r.source = '{source}'
        """
    
    async def store_entities(
        self,
        entities: list[GroundedEntity],
        source: str,
        batch_size: int = 50,
    ) -> int:
        """
        Store grounded entities as Neo4j nodes with properties.
        
        Args:
            entities: List of GroundedEntity objects
            source: Source document identifier
            batch_size: Entities per batch
            
        Returns:
            Number of nodes created/updated
        """
        if not entities:
            return 0
        
        stored = 0
        
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            statements = []
            
            for entity in batch:
                cypher = self._build_entity_cypher(entity, source)
                statements.append({"statement": cypher})
            
            try:
                await self.neo4j.execute_batch(statements)
                stored += len(batch)
            except Exception:
                continue
        
        return stored
    
    def _build_entity_cypher(
        self,
        entity: GroundedEntity,
        source: str,
    ) -> str:
        """Build Cypher MERGE for grounded entity."""
        label = entity.entity_class.value.title().replace("_", "")
        text = self._sanitize(entity.text)
        
        # Build properties
        props = {
            "text": entity.text,
            "entity_class": entity.entity_class.value,
            "start_offset": entity.start_offset,
            "end_offset": entity.end_offset,
            "confidence": entity.confidence,
            "source": source,
        }
        props.update(entity.attributes)
        
        props_str = ", ".join(
            f"n.{k} = {self._cypher_value(v)}"
            for k, v in props.items()
        )
        
        return f"""
        MERGE (n:{label} {{text: '{text}'}})
        ON CREATE SET {props_str}, n.created_at = datetime()
        ON MATCH SET n.updated_at = datetime()
        """
    
    async def store_result(
        self,
        result: ExtractionResult,
    ) -> dict[str, int]:
        """
        Store complete extraction result.
        
        Args:
            result: ExtractionResult from pipeline
            
        Returns:
            Dict with counts of stored items
        """
        triple_count = await self.store_triples(
            result.triples,
            source=result.source_document,
        )
        
        entity_count = await self.store_entities(
            result.grounded_entities,
            source=result.source_document,
        )
        
        return {
            "triples_stored": triple_count,
            "entities_stored": entity_count,
        }
    
    async def store_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        source: str,
        collection: str = "gdpr_chunks",
    ) -> int:
        """
        Store chunks with embeddings in Qdrant for hybrid RAG.
        
        Args:
            chunks: Text chunks
            embeddings: Vector embeddings (same length as chunks)
            source: Source document identifier
            collection: Qdrant collection name
            
        Returns:
            Number of points stored
        """
        if not self.qdrant or not chunks or not embeddings:
            return 0
        
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have same length")
        
        try:
            from qdrant_client.models import PointStruct
            
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                points.append(PointStruct(
                    id=f"{source}_{chunk.chunk_index}",
                    vector=embedding,
                    payload={
                        "text": chunk.text,
                        "start_offset": chunk.start_offset,
                        "end_offset": chunk.end_offset,
                        "chunk_index": chunk.chunk_index,
                        "source": source,
                    }
                ))
            
            await self.qdrant.upsert(
                collection_name=collection,
                points=points,
            )
            
            return len(points)
            
        except Exception:
            return 0
    
    async def search_similar(
        self,
        query_embedding: list[float],
        collection: str = "gdpr_chunks",
        limit: int = 10,
    ) -> list[TextChunk]:
        """
        Search for similar chunks by embedding.
        
        Args:
            query_embedding: Query vector
            collection: Qdrant collection name
            limit: Maximum results
            
        Returns:
            List of TextChunk objects ordered by similarity
        """
        if not self.qdrant:
            return []
        
        try:
            results = await self.qdrant.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=limit,
            )
            
            chunks = []
            for result in results:
                payload = result.payload
                chunks.append(TextChunk(
                    text=payload.get("text", ""),
                    start_offset=payload.get("start_offset", 0),
                    end_offset=payload.get("end_offset", 0),
                    chunk_index=payload.get("chunk_index", 0),
                    word_count=len(payload.get("text", "").split()),
                ))
            
            return chunks
            
        except Exception:
            return []
    
    def _sanitize(self, text: str) -> str:
        """Sanitize string for Cypher."""
        return text.replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
    
    def _cypher_value(self, value: Any) -> str:
        """Convert Python value to Cypher literal."""
        if isinstance(value, str):
            return f"'{self._sanitize(value)}'"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return "null"
        else:
            return f"'{self._sanitize(str(value))}'"


# =============================================================================
# Query Functions
# =============================================================================

async def get_entity_relationships(
    neo4j_client,
    entity_name: str,
    limit: int = 50,
) -> list[dict]:
    """
    Get all relationships for an entity.
    
    Args:
        neo4j_client: Neo4jClient instance
        entity_name: Name of entity to query
        limit: Maximum relationships
        
    Returns:
        List of relationship dicts
    """
    cypher = f"""
    MATCH (e:Entity {{name: $name}})-[r]->(t)
    RETURN e.name as subject, type(r) as predicate, t.name as object,
           r.confidence as confidence, r.inferred as inferred
    LIMIT $limit
    UNION
    MATCH (s)-[r]->(e:Entity {{name: $name}})
    RETURN s.name as subject, type(r) as predicate, e.name as object,
           r.confidence as confidence, r.inferred as inferred
    LIMIT $limit
    """
    
    return await neo4j_client.query(cypher, {"name": entity_name, "limit": limit})


async def get_graph_data(
    neo4j_client,
    source_filter: Optional[str] = None,
    limit: int = 500,
) -> dict:
    """
    Get graph data for visualization.
    
    Args:
        neo4j_client: Neo4jClient instance
        source_filter: Optional filter by source
        limit: Maximum nodes
        
    Returns:
        Dict with nodes and edges for force graph
    """
    where_clause = "WHERE r.source = $source" if source_filter else ""
    
    cypher = f"""
    MATCH (s:Entity)-[r]->(t:Entity)
    {where_clause}
    RETURN s.name as source_name, type(r) as relationship, 
           t.name as target_name, r.confidence as confidence,
           r.inferred as inferred
    LIMIT $limit
    """
    
    params = {"limit": limit}
    if source_filter:
        params["source"] = source_filter
    
    results = await neo4j_client.query(cypher, params)
    
    # Convert to force graph format
    nodes = {}
    edges = []
    
    for row in results:
        source = row["source_name"]
        target = row["target_name"]
        
        if source not in nodes:
            nodes[source] = {"id": source, "label": source}
        if target not in nodes:
            nodes[target] = {"id": target, "label": target}
        
        edges.append({
            "source": source,
            "target": target,
            "label": row["relationship"],
            "confidence": row.get("confidence", 1.0),
            "inferred": row.get("inferred", False),
        })
    
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }
