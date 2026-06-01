"""
Graph Inspired Veracity Extrapolator (GIVE Pattern)

Implements the GIVE framework from "Structured Reasoning with Knowledge Graph
Inspired Veracity Extrapolation" for enhanced reasoning on sparse KGs.

Key Concepts:
1. Entity Group Construction: Group semantically similar KG concepts
2. Inner-Group Connections: LLM infers relations within concept groups
3. Inter-Group Connections: Probe potential relations across groups via KG hints
4. Veracity Extrapolation: Yes/No/Maybe labels for potential relations

Reference: https://arxiv.org/abs/2410.03772
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Literal
from collections import defaultdict

from .schemas import SPOTriple


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class EntityGroup:
    """
    Group of semantically related entities (GIVE pattern).
    
    Entity groups enable multi-hop reasoning by clustering similar
    concepts and inferring connections within and across groups.
    """
    queried_entity: str           # The original queried entity
    related_entities: list[str]   # Similar entities from KG
    inner_connections: list[str]  # Inferred relations within group
    confidence: float = 0.5


@dataclass
class ExtrapolatedEdge:
    """
    An extrapolated relationship with veracity label (GIVE pattern).
    
    Unlike directly extracted triples, these are inferred relationships
    with explicit uncertainty quantification.
    """
    source: str
    relation: str
    target: str
    veracity: Literal["yes", "no", "maybe"]
    is_factual: bool = False       # True if confirmed by KG evidence
    is_counterfactual: bool = False  # True if explicitly negated
    explanation: str = ""


@dataclass
class ReasoningChain:
    """
    Multi-hop reasoning chain through entity groups (GIVE pattern).
    
    Captures the path from source to target through intermediate
    entities and their connections.
    """
    source_group: EntityGroup
    target_group: EntityGroup
    intermediate_nodes: list[str]
    extrapolated_edges: list[ExtrapolatedEdge]
    chain_confidence: float


# =============================================================================
# Veracity Extrapolator Class
# =============================================================================

class VeracityExtrapolator:
    """
    Graph Inspired Veracity Extrapolation (GIVE) for sparse KG reasoning.
    
    This addresses the "sparse KG" problem where extracted knowledge graphs
    have insufficient connections for complex reasoning. GIVE augments the
    KG with extrapolated relationships using LLM reasoning.
    
    Key Methods:
    - build_entity_groups(): Construct groups of similar KG concepts
    - extrapolate_veracity(): Probe potential relations with yes/no/maybe
    - build_reasoning_chain(): Multi-hop path through entity groups
    
    Usage:
        extrapolator = VeracityExtrapolator(gemini_client, neo4j_client)
        groups = await extrapolator.build_entity_groups(query_entities)
        edges = await extrapolator.extrapolate_veracity(groups, relations)
    """
    
    def __init__(
        self,
        gemini_client=None,
        neo4j_client=None,
        max_group_size: int = 3,
    ):
        """
        Initialize the veracity extrapolator.
        
        Args:
            gemini_client: GeminiClient for LLM reasoning
            neo4j_client: Neo4j client for KG queries
            max_group_size: Maximum entities per group
        """
        self.client = gemini_client
        self.neo4j = neo4j_client
        self.max_group_size = max_group_size
    
    async def build_entity_groups(
        self,
        entities: list[str],
        existing_triples: list[SPOTriple],
    ) -> dict[str, EntityGroup]:
        """
        Construct entity groups by finding semantically similar KG concepts.
        
        For each query entity, finds related entities from the KG that
        could support multi-hop reasoning (GIVE Step 1).
        
        Args:
            entities: List of queried entities
            existing_triples: Current KG triples for relationship lookup
            
        Returns:
            Dict mapping entity names to EntityGroup objects
        """
        groups = {}
        
        # Build entity adjacency from triples
        adjacency: dict[str, set[str]] = defaultdict(set)
        for triple in existing_triples:
            subj_lower = triple.subject.lower()
            obj_lower = triple.object.lower()
            adjacency[subj_lower].add(obj_lower)
            adjacency[obj_lower].add(subj_lower)
        
        for entity in entities:
            entity_lower = entity.lower()
            
            # Find directly connected entities
            related = list(adjacency.get(entity_lower, set()))[:self.max_group_size]
            
            # If no direct connections, try semantic matching
            if not related and self.client:
                related = await self._find_similar_entities(
                    entity, existing_triples
                )
            
            # Infer inner-group connections
            inner_connections = await self._induce_inner_connections(
                entity, related, existing_triples
            )
            
            groups[entity] = EntityGroup(
                queried_entity=entity,
                related_entities=related,
                inner_connections=inner_connections,
                confidence=0.8 if related else 0.4,
            )
        
        return groups
    
    async def extrapolate_veracity(
        self,
        source_group: EntityGroup,
        target_group: EntityGroup,
        potential_relations: list[str],
    ) -> list[ExtrapolatedEdge]:
        """
        Probe and prune potential relations between entity groups (GIVE Step 2).
        
        For each source entity and target entity pair, probes whether
        potential relations hold using yes/no/maybe classification.
        
        Args:
            source_group: Source entity group
            target_group: Target entity group
            potential_relations: List of relation types to probe
            
        Returns:
            List of ExtrapolatedEdge with veracity labels
        """
        if not self.client:
            return []
        
        edges = []
        
        # Get all entities to probe
        source_entities = [source_group.queried_entity] + source_group.related_entities
        target_entities = [target_group.queried_entity] + target_group.related_entities
        
        # Limit combinations for efficiency
        for src in source_entities[:2]:
            for tgt in target_entities[:2]:
                if src.lower() == tgt.lower():
                    continue
                
                for relation in potential_relations[:3]:
                    edge = await self._probe_relation(src, relation, tgt)
                    edges.append(edge)
        
        return edges
    
    async def build_reasoning_chain(
        self,
        source: str,
        target: str,
        triples: list[SPOTriple],
        max_hops: int = 2,
    ) -> Optional[ReasoningChain]:
        """
        Build multi-hop reasoning chain between source and target (GIVE Step 3).
        
        Discovers intermediate nodes that connect source to target,
        enabling reasoning over paths longer than 1 hop.
        
        Args:
            source: Source entity
            target: Target entity
            triples: Available KG triples
            max_hops: Maximum path length
            
        Returns:
            ReasoningChain if path found, None otherwise
        """
        # Build groups for source and target
        groups = await self.build_entity_groups([source, target], triples)
        source_group = groups.get(source)
        target_group = groups.get(target)
        
        if not source_group or not target_group:
            return None
        
        # Find intermediate nodes via graph traversal
        intermediates = self._find_intermediate_nodes(
            source, target, triples, max_hops
        )
        
        if not intermediates:
            # Try to extrapolate direct connection
            common_relations = ["RELATES_TO", "ASSOCIATED_WITH", "CONNECTED_TO"]
            edges = await self.extrapolate_veracity(
                source_group, target_group, common_relations
            )
            
            return ReasoningChain(
                source_group=source_group,
                target_group=target_group,
                intermediate_nodes=[],
                extrapolated_edges=edges,
                chain_confidence=0.5 if edges else 0.2,
            )
        
        # Build edges along the path
        edges = []
        for i, node in enumerate(intermediates):
            prev = source if i == 0 else intermediates[i-1]
            edges.append(ExtrapolatedEdge(
                source=prev,
                relation="CONNECTS_TO",
                target=node,
                veracity="yes",
                is_factual=True,
            ))
        
        # Final edge to target
        if intermediates:
            edges.append(ExtrapolatedEdge(
                source=intermediates[-1],
                relation="CONNECTS_TO",
                target=target,
                veracity="yes",
                is_factual=True,
            ))
        
        return ReasoningChain(
            source_group=source_group,
            target_group=target_group,
            intermediate_nodes=intermediates,
            extrapolated_edges=edges,
            chain_confidence=0.8,
        )
    
    async def discover_intermediate_nodes(
        self,
        source: str,
        target: str,
        triples: list[SPOTriple],
    ) -> list[str]:
        """
        Find intermediate nodes for multi-hop reasoning.
        
        Public interface to the internal path-finding algorithm,
        exposed for use by other modules.
        
        Args:
            source: Source entity
            target: Target entity
            triples: Available triples
            
        Returns:
            List of intermediate node names
        """
        return self._find_intermediate_nodes(source, target, triples, max_hops=2)
    
    async def _find_similar_entities(
        self,
        entity: str,
        triples: list[SPOTriple],
    ) -> list[str]:
        """Use LLM to find semantically similar entities."""
        if not self.client:
            return []
        
        # Get all entities from triples
        all_entities = set()
        for t in triples:
            all_entities.add(t.subject)
            all_entities.add(t.object)
        
        if not all_entities:
            return []
        
        entities_list = list(all_entities)[:30]  # Limit for prompt
        
        prompt = f"""Given the entity "{entity}", find the 2 most semantically similar entities from this list:

ENTITIES: {', '.join(entities_list)}

Return a JSON array with just the entity names:
["entity1", "entity2"]

Only include entities that are genuinely similar in meaning or function to "{entity}".
"""
        
        try:
            response = await self.client.extract_json(prompt)
            if isinstance(response, list):
                return [str(e) for e in response[:self.max_group_size]]
        except Exception:
            pass
        
        return []
    
    async def _induce_inner_connections(
        self,
        entity: str,
        related: list[str],
        triples: list[SPOTriple],
    ) -> list[str]:
        """Induce connections within an entity group."""
        connections = []
        
        # Check for existing relationships
        for triple in triples:
            subj_lower = triple.subject.lower()
            obj_lower = triple.object.lower()
            
            entity_set = {entity.lower()} | {r.lower() for r in related}
            
            if subj_lower in entity_set and obj_lower in entity_set:
                connections.append(
                    f"{triple.subject} --[{triple.predicate}]--> {triple.object}"
                )
        
        return connections[:5]  # Limit to 5 connections
    
    async def _probe_relation(
        self,
        source: str,
        relation: str,
        target: str,
    ) -> ExtrapolatedEdge:
        """
        Probe whether a specific relation holds between two entities.
        
        Uses yes/no/maybe classification for explicit uncertainty.
        """
        if not self.client:
            return ExtrapolatedEdge(
                source=source,
                relation=relation,
                target=target,
                veracity="maybe",
                explanation="No LLM available for probing",
            )
        
        prompt = f"""Does the following relationship hold in the context of privacy policies and data handling?

Subject: {source}
Relation: {relation}
Object: {target}

Answer with exactly one of: yes, no, maybe

Then provide brief reasoning (1 sentence).

Format your response as JSON:
{{"verdict": "yes|no|maybe", "explanation": "Your reasoning"}}
"""
        
        try:
            response = await self.client.extract_json(prompt)
            
            verdict = response.get("verdict", "maybe").lower()
            if verdict not in ("yes", "no", "maybe"):
                verdict = "maybe"
            
            return ExtrapolatedEdge(
                source=source,
                relation=relation,
                target=target,
                veracity=verdict,
                is_factual=verdict == "yes",
                is_counterfactual=verdict == "no",
                explanation=response.get("explanation", ""),
            )
            
        except Exception as e:
            return ExtrapolatedEdge(
                source=source,
                relation=relation,
                target=target,
                veracity="maybe",
                explanation=f"Probe failed: {str(e)}",
            )
    
    def _find_intermediate_nodes(
        self,
        source: str,
        target: str,
        triples: list[SPOTriple],
        max_hops: int,
    ) -> list[str]:
        """
        Find intermediate nodes connecting source to target.
        
        Uses BFS to find shortest path up to max_hops.
        """
        # Build adjacency list
        adjacency: dict[str, set[str]] = defaultdict(set)
        for triple in triples:
            subj_lower = triple.subject.lower()
            obj_lower = triple.object.lower()
            adjacency[subj_lower].add(obj_lower)
            adjacency[obj_lower].add(subj_lower)
        
        source_lower = source.lower()
        target_lower = target.lower()
        
        # BFS for shortest path
        if source_lower == target_lower:
            return []
        
        queue: list[tuple[str, list[str]]] = [(source_lower, [])]
        visited = {source_lower}
        
        while queue:
            current, path = queue.pop(0)
            
            if len(path) >= max_hops:
                continue
            
            for neighbor in adjacency.get(current, set()):
                if neighbor == target_lower:
                    return path  # Found path, return intermediates
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return []  # No path found


# =============================================================================
# Convenience Functions
# =============================================================================

async def extrapolate_relations(
    source: str,
    target: str,
    relations: list[str],
    triples: list[SPOTriple],
    gemini_client,
) -> list[ExtrapolatedEdge]:
    """
    Quick veracity extrapolation between two entities.
    
    Args:
        source: Source entity
        target: Target entity
        relations: Relations to probe
        triples: Current KG triples
        gemini_client: Gemini client
        
    Returns:
        List of extrapolated edges with veracity labels
    """
    extrapolator = VeracityExtrapolator(gemini_client)
    groups = await extrapolator.build_entity_groups([source, target], triples)
    
    source_group = groups.get(source)
    target_group = groups.get(target)
    
    if not source_group or not target_group:
        return []
    
    return await extrapolator.extrapolate_veracity(
        source_group, target_group, relations
    )


async def find_reasoning_path(
    source: str,
    target: str,
    triples: list[SPOTriple],
    gemini_client=None,
) -> Optional[ReasoningChain]:
    """
    Build multi-hop reasoning chain between entities.
    
    Args:
        source: Source entity
        target: Target entity
        triples: Available triples
        gemini_client: Optional Gemini client
        
    Returns:
        ReasoningChain if path found
    """
    extrapolator = VeracityExtrapolator(gemini_client)
    return await extrapolator.build_reasoning_chain(source, target, triples)
