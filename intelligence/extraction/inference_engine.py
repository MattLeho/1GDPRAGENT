"""
Relationship Inference Engine

Implements AI-KG Phase 3 relationship inference with multiple methods:
- Transitive inference (A→B→C implies A→C)
- Community detection (Louvain algorithm via NetworkX)
- LLM-assisted cross-community inference
- Within-community relationship inference
- Lexical similarity matching

Key Features:
- Configurable inference methods
- Marks inferred triples for visualization (dashed edges)
- Deduplication and self-reference filtering

Source patterns: https://github.com/robert-mcdermott/ai-knowledge-graph
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass, field

from .schemas import SPOTriple, InferenceConfig
from .spo_extractor import normalize_predicate


# =============================================================================
# Constants
# =============================================================================

# Common relationship predicates for transitive inference
TRANSITIVE_RELATIONS = frozenset({
    "SHARES_WITH", "TRANSFERS_TO", "SENDS_TO", "PROVIDES_TO",
    "CONNECTS_TO", "LINKS_TO", "ASSOCIATED_WITH"
})

# Similarity threshold for lexical matching
DEFAULT_SIMILARITY_THRESHOLD = 0.8


# =============================================================================
# Inference Engine Class
# =============================================================================

class InferenceEngine:
    """
    Infers additional relationships from extracted triples.
    
    Implements AI-KG Phase 3 inference pipeline including:
    - Community detection to identify related entity clusters
    - Transitive inference for relationship chains
    - LLM-assisted inference for cross-community linking
    - Lexical similarity for semantic relationships
    
    Usage:
        engine = InferenceEngine(gemini_client)
        enriched = await engine.infer_relationships(triples, config)
    """
    
    def __init__(
        self,
        gemini_client=None,
    ):
        """
        Initialize inference engine.
        
        Args:
            gemini_client: Optional GeminiClient for LLM-assisted inference
        """
        self.client = gemini_client
    
    async def infer_relationships(
        self,
        triples: list[SPOTriple],
        config: Optional[InferenceConfig] = None,
    ) -> list[SPOTriple]:
        """
        Infer additional relationships from input triples.
        
        Follows AI-KG infer_relationships pattern with all inference methods.
        
        Args:
            triples: Input triples
            config: Inference configuration
            
        Returns:
            Triples with inferred relationships added
        """
        config = config or InferenceConfig()
        
        if not triples:
            return triples
        
        # Validate input triples
        valid_triples = [
            t for t in triples
            if t.subject and t.predicate and t.object
        ]
        
        if not valid_triples:
            return []
        
        # Build graph structure
        graph = self._build_graph(valid_triples)
        
        # Extract all entities
        all_entities = set()
        for triple in valid_triples:
            all_entities.add(triple.subject.lower())
            all_entities.add(triple.object.lower())
        
        # Identify communities
        communities = self._identify_communities(graph)
        
        # Collect new inferred triples
        new_triples = []
        
        # 1. LLM-based community inference (if enabled)
        if config.use_llm_for_inference and self.client:
            # Cross-community inference
            community_triples = await self._infer_with_llm(
                valid_triples, communities, config
            )
            new_triples.extend(community_triples)
            
            # Within-community inference
            within_triples = await self._infer_within_community(
                valid_triples, communities, config
            )
            new_triples.extend(within_triples)
        
        # 2. Transitive inference (if enabled)
        if config.apply_transitive:
            transitive_triples = self._apply_transitive_inference(
                valid_triples, graph, config
            )
            new_triples.extend(transitive_triples)
        
        # 3. Lexical similarity (if enabled)
        if config.use_lexical_similarity:
            lexical_triples = self._infer_by_lexical_similarity(
                all_entities, valid_triples, config
            )
            new_triples.extend(lexical_triples)
        
        # Combine original and inferred triples
        if new_triples:
            valid_triples.extend(new_triples)
        
        # Deduplicate
        unique_triples = self._deduplicate_triples(valid_triples)
        
        # Enforce predicate word limit
        result = []
        for triple in unique_triples:
            normalized_pred = normalize_predicate(
                triple.predicate, 
                max_words=config.max_predicate_words
            )
            if normalized_pred != triple.predicate:
                result.append(SPOTriple(
                    subject=triple.subject,
                    predicate=normalized_pred,
                    object=triple.object,
                    confidence=triple.confidence,
                    source_chunk=triple.source_chunk,
                    source_text=triple.source_text,
                    inferred=triple.inferred,
                ))
            else:
                result.append(triple)
        
        # Filter self-references
        filtered = self._filter_self_references(result)
        
        return filtered
    
    def _build_graph(
        self,
        triples: list[SPOTriple],
    ) -> dict[str, set[str]]:
        """
        Build adjacency graph from triples.
        
        Returns dict mapping subject to set of objects.
        """
        graph = defaultdict(set)
        
        for triple in triples:
            subj = triple.subject.lower()
            obj = triple.object.lower()
            graph[subj].add(obj)
        
        return dict(graph)
    
    def _identify_communities(
        self,
        graph: dict[str, set[str]],
    ) -> list[set[str]]:
        """
        Identify disconnected communities using DFS.
        
        Following AI-KG _identify_communities pattern.
        Returns list of sets, each containing nodes in a community.
        """
        # Get all nodes (both subjects and objects)
        all_nodes = set(graph.keys())
        for targets in graph.values():
            all_nodes.update(targets)
        
        visited = set()
        communities = []
        
        def dfs(node: str, community: set):
            """Depth-first search to find connected component."""
            visited.add(node)
            community.add(node)
            
            # Visit outgoing edges
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, community)
            
            # Visit incoming edges
            for source, targets in graph.items():
                if node in targets and source not in visited:
                    dfs(source, community)
        
        # Find all communities
        for node in all_nodes:
            if node not in visited:
                community = set()
                dfs(node, community)
                communities.append(community)
        
        return communities
    
    def detect_communities_louvain(
        self,
        triples: list[SPOTriple],
    ) -> list[set[str]]:
        """
        Detect communities using Louvain algorithm (NetworkX).
        
        Higher quality community detection for larger graphs.
        Requires networkx with community detection support.
        """
        try:
            import networkx as nx
            from networkx.algorithms import community as nx_community
        except ImportError:
            # Fall back to DFS-based detection
            graph = self._build_graph(triples)
            return self._identify_communities(graph)
        
        # Build NetworkX graph
        G = nx.Graph()
        
        for triple in triples:
            subj = triple.subject.lower()
            obj = triple.object.lower()
            G.add_edge(subj, obj, weight=triple.confidence)
        
        # Apply Louvain algorithm
        try:
            partition = nx_community.louvain_communities(G)
            return [set(c) for c in partition]
        except Exception:
            # Fall back on error
            graph = self._build_graph(triples)
            return self._identify_communities(graph)
    
    def _apply_transitive_inference(
        self,
        triples: list[SPOTriple],
        graph: dict[str, set[str]],
        config: InferenceConfig,
    ) -> list[SPOTriple]:
        """
        Apply transitive inference: A→B→C implies A→C.
        
        Following AI-KG _apply_transitive_inference pattern.
        """
        new_triples = []
        
        # Build predicate lookup
        predicates = {}
        for triple in triples:
            key = (triple.subject.lower(), triple.object.lower())
            predicates[key] = triple.predicate
        
        # Find transitive relationships
        for subj in graph:
            for mid in graph.get(subj, set()):
                for obj in graph.get(mid, set()):
                    # Only consider if A != C and no direct A→C exists
                    if subj != obj and (subj, obj) not in predicates:
                        # Get predicates for the path
                        pred1 = predicates.get((subj, mid), "RELATES_TO")
                        pred2 = predicates.get((mid, obj), "RELATES_TO")
                        
                        # Generate transitive predicate
                        if pred1 == pred2:
                            new_pred = f"INDIRECTLY_{pred1}"
                        else:
                            # Use shorter form to respect word limit
                            new_pred = f"VIA_{mid.upper().replace(' ', '_')[:10]}"
                        
                        new_pred = normalize_predicate(
                            new_pred, 
                            max_words=config.max_predicate_words
                        )
                        
                        new_triples.append(SPOTriple(
                            subject=subj,
                            predicate=new_pred,
                            object=obj,
                            confidence=0.6,  # Lower confidence for transitive
                            source_chunk=None,
                            source_text=None,
                            inferred=True,
                        ))
        
        return new_triples
    
    async def _infer_with_llm(
        self,
        triples: list[SPOTriple],
        communities: list[set[str]],
        config: InferenceConfig,
    ) -> list[SPOTriple]:
        """
        Use LLM to infer relationships between disconnected communities.
        
        Following AI-KG _infer_relationships_with_llm pattern.
        """
        if not self.client or len(communities) < 2:
            return []
        
        new_triples = []
        
        # Get representative entities from each community
        community_reps = []
        for community in communities:
            if len(community) > 0:
                # Take up to 3 representatives per community
                reps = list(community)[:3]
                community_reps.append(reps)
        
        # Build prompt for cross-community inference
        if len(community_reps) < 2:
            return []
        
        communities_text = "\n".join(
            f"Community {i+1}: {', '.join(reps)}"
            for i, reps in enumerate(community_reps[:5])  # Max 5 communities
        )
        
        prompt = f"""Given these entity communities from a knowledge graph, identify any plausible relationships BETWEEN communities that might exist but weren't explicitly stated.

COMMUNITIES:
{communities_text}

What relationships might exist between entities in different communities? Consider data sharing, ownership, partnerships, or other connections.

Return a JSON array of relationships with format:
[{{"subject": "entity1", "predicate": "RELATIONSHIP_TYPE", "object": "entity2", "confidence": 0.7}}]

Only return relationships you're reasonably confident exist. Use UPPERCASE_SNAKE_CASE for predicates (max 3 words)."""
        
        try:
            response = await self.client.extract_json(prompt)
            
            if isinstance(response, list):
                for item in response[:10]:  # Max 10 inferences
                    if all(k in item for k in ["subject", "predicate", "object"]):
                        new_triples.append(SPOTriple(
                            subject=str(item["subject"]),
                            predicate=normalize_predicate(
                                str(item["predicate"]),
                                max_words=config.max_predicate_words
                            ),
                            object=str(item["object"]),
                            confidence=float(item.get("confidence", 0.5)),
                            source_chunk=None,
                            source_text=None,
                            inferred=True,
                        ))
            
            return new_triples
            
        except Exception:
            return []
    
    async def _infer_within_community(
        self,
        triples: list[SPOTriple],
        communities: list[set[str]],
        config: InferenceConfig,
    ) -> list[SPOTriple]:
        """
        Infer relationships within the same community.
        
        Entities in the same community are likely related.
        """
        if not self.client:
            return []
        
        new_triples = []
        
        # Get existing relationships
        existing = {
            (t.subject.lower(), t.object.lower())
            for t in triples
        }
        
        # For each community with multiple entities
        for community in communities:
            if len(community) < 3:
                continue
            
            # Get entities without direct relationships
            entities = list(community)[:10]  # Limit for prompt size
            
            if len(entities) < 3:
                continue
            
            prompt = f"""These entities appear in the same community in a knowledge graph, suggesting they're related:

ENTITIES: {', '.join(entities)}

What relationships might exist between these entities that weren't explicitly stated? Focus on data privacy and GDPR-relevant relationships.

Return a JSON array with format:
[{{"subject": "entity1", "predicate": "RELATIONSHIP_TYPE", "object": "entity2", "confidence": 0.6}}]

Use UPPERCASE_SNAKE_CASE for predicates (max 3 words). Only include high-confidence relationships."""
            
            try:
                response = await self.client.extract_json(prompt)
                
                if isinstance(response, list):
                    for item in response[:5]:  # Max 5 per community
                        if all(k in item for k in ["subject", "predicate", "object"]):
                            subj = str(item["subject"]).lower()
                            obj = str(item["object"]).lower()
                            
                            # Skip if relationship already exists
                            if (subj, obj) in existing or (obj, subj) in existing:
                                continue
                            
                            new_triples.append(SPOTriple(
                                subject=str(item["subject"]),
                                predicate=normalize_predicate(
                                    str(item["predicate"]),
                                    max_words=config.max_predicate_words
                                ),
                                object=str(item["object"]),
                                confidence=float(item.get("confidence", 0.5)),
                                source_chunk=None,
                                source_text=None,
                                inferred=True,
                            ))
                            
            except Exception:
                continue
        
        return new_triples
    
    def _infer_by_lexical_similarity(
        self,
        entities: set[str],
        triples: list[SPOTriple],
        config: InferenceConfig,
    ) -> list[SPOTriple]:
        """
        Infer relationships based on lexical similarity.
        
        Entities with similar names might be related.
        """
        new_triples = []
        
        # Get existing relationships
        existing = {
            (t.subject.lower(), t.object.lower())
            for t in triples
        }
        
        entity_list = list(entities)
        
        for i, entity1 in enumerate(entity_list):
            for entity2 in entity_list[i+1:]:
                # Skip if relationship exists
                if (entity1, entity2) in existing or (entity2, entity1) in existing:
                    continue
                
                # Calculate simple similarity (shared words)
                words1 = set(entity1.lower().split())
                words2 = set(entity2.lower().split())
                
                if not words1 or not words2:
                    continue
                
                shared = words1 & words2
                union = words1 | words2
                
                similarity = len(shared) / len(union) if union else 0
                
                if similarity >= config.similarity_threshold:
                    new_triples.append(SPOTriple(
                        subject=entity1,
                        predicate="SIMILAR_TO",
                        object=entity2,
                        confidence=similarity,
                        source_chunk=None,
                        source_text=None,
                        inferred=True,
                    ))
        
        return new_triples
    
    def _deduplicate_triples(
        self,
        triples: list[SPOTriple],
    ) -> list[SPOTriple]:
        """
        Remove duplicate triples, keeping highest confidence.
        """
        seen: dict[tuple, SPOTriple] = {}
        
        for triple in triples:
            key = (
                triple.subject.lower(),
                triple.predicate.upper(),
                triple.object.lower(),
            )
            
            if key not in seen:
                seen[key] = triple
            elif triple.confidence > seen[key].confidence:
                seen[key] = triple
        
        return list(seen.values())
    
    def _filter_self_references(
        self,
        triples: list[SPOTriple],
    ) -> list[SPOTriple]:
        """
        Remove triples where subject equals object.
        """
        return [
            t for t in triples
            if t.subject.lower() != t.object.lower()
        ]


# =============================================================================
# Convenience Functions
# =============================================================================

async def infer_relationships(
    triples: list[SPOTriple],
    gemini_client=None,
    use_llm: bool = True,
) -> list[SPOTriple]:
    """
    Quick relationship inference with default settings.
    """
    config = InferenceConfig(use_llm_for_inference=use_llm and gemini_client is not None)
    engine = InferenceEngine(gemini_client)
    return await engine.infer_relationships(triples, config)
