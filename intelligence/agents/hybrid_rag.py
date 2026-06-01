"""
Hybrid RAG Agent

Translates 10_hybrid_rag.json N8N workflow to Python.
Combines vector search (Qdrant) with graph traversal (Neo4j) for enhanced retrieval.
"""

import json
from typing import Optional
from dataclasses import dataclass, field

from llm.gemini import GeminiClient
from db.neo4j import get_neo4j_client
from config import get_settings


settings = get_settings()


@dataclass
class SearchResult:
    """Single search result from hybrid RAG."""
    content: str
    source: str  # "vector" or "graph"
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Combined results from hybrid search."""
    query: str
    results: list[SearchResult] = field(default_factory=list)
    vector_count: int = 0
    graph_count: int = 0
    generated_answer: Optional[str] = None


class HybridRAGAgent:
    """
    Hybrid RAG Agent - Vector + Graph Search.
    
    Translates 10_hybrid_rag.json N8N workflow to Python.
    
    Pipeline:
    1. Query Qdrant for semantic matches
    2. Query Neo4j for graph context
    3. Merge and rank results
    4. Generate response with Gemini
    """
    
    def __init__(self):
        """Initialize the Hybrid RAG agent."""
        self.llm = GeminiClient.get_flash_client()
        self.neo4j = get_neo4j_client()
        self.qdrant_url = settings.qdrant_url
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        include_graph: bool = True,
        include_vectors: bool = True,
        generate_answer: bool = True,
    ) -> HybridSearchResult:
        """
        Perform hybrid search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            include_graph: Include Neo4j graph results
            include_vectors: Include Qdrant vector results
            generate_answer: Generate LLM answer from results
            
        Returns:
            HybridSearchResult with merged results
        """
        results = []
        vector_count = 0
        graph_count = 0
        
        # Vector search (Qdrant)
        if include_vectors:
            vector_results = await self._vector_search(query, top_k)
            results.extend(vector_results)
            vector_count = len(vector_results)
        
        # Graph search (Neo4j)
        if include_graph:
            graph_results = await self._graph_search(query, top_k)
            results.extend(graph_results)
            graph_count = len(graph_results)
        
        # Sort by score and deduplicate
        results = self._merge_and_rank(results, top_k)
        
        # Generate answer if requested
        generated_answer = None
        if generate_answer and results:
            generated_answer = await self._generate_answer(query, results)
        
        return HybridSearchResult(
            query=query,
            results=results,
            vector_count=vector_count,
            graph_count=graph_count,
            generated_answer=generated_answer,
        )
    
    async def _vector_search(
        self,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        """Search Qdrant for semantically similar content."""
        results = []
        
        try:
            import httpx
            
            # First, get embedding for query (using Gemini)
            # Note: In production, use a proper embedding model
            embedding = await self._get_query_embedding(query)
            
            if not embedding:
                return results
            
            # Search Qdrant
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.qdrant_url}/collections/gdpr_chunks/points/search",
                    json={
                        "vector": embedding,
                        "limit": top_k,
                        "with_payload": True,
                    },
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for point in data.get("result", []):
                        payload = point.get("payload", {})
                        results.append(SearchResult(
                            content=payload.get("text", ""),
                            source="vector",
                            score=point.get("score", 0.0),
                            metadata={
                                "chunk_id": point.get("id"),
                                "source_file": payload.get("source_file"),
                                "company": payload.get("company"),
                            },
                        ))
        except Exception as e:
            # Vector search failed, continue with graph only
            pass
        
        return results
    
    async def _get_query_embedding(self, query: str) -> Optional[list[float]]:
        """Get embedding for query (placeholder - needs embedding model)."""
        # TODO: Implement proper embedding with Gemini embedding API
        # For now, return None to skip vector search
        return None
    
    async def _graph_search(
        self,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        """Search Neo4j for relevant graph data."""
        results = []
        
        # Extract keywords for graph search
        keywords = self._extract_keywords(query)
        
        try:
            # Full-text search across nodes
            for keyword in keywords[:3]:
                graph_query = """
                MATCH (n)
                WHERE any(prop in keys(n) WHERE 
                    toLower(toString(n[prop])) CONTAINS toLower($keyword))
                WITH n, labels(n) as labels
                OPTIONAL MATCH (n)-[r]-(connected)
                RETURN labels, properties(n) as props, 
                       type(r) as rel_type, labels(connected) as connected_labels
                LIMIT $limit
                """
                
                records = await self.neo4j.query(
                    graph_query,
                    {"keyword": keyword, "limit": top_k // 3},
                )
                
                for record in records:
                    content = json.dumps({
                        "node": record.get("props", {}),
                        "labels": record.get("labels", []),
                        "relationship": record.get("rel_type"),
                        "connected_to": record.get("connected_labels"),
                    })
                    
                    results.append(SearchResult(
                        content=content,
                        source="graph",
                        score=0.8,  # Graph results get high base score
                        metadata={
                            "keyword": keyword,
                            "labels": record.get("labels", []),
                        },
                    ))
        except Exception:
            pass
        
        return results
    
    def _extract_keywords(self, query: str) -> list[str]:
        """Extract keywords from query."""
        stopwords = {
            "who", "what", "where", "when", "why", "how",
            "is", "are", "was", "were", "has", "have", "had",
            "my", "the", "a", "an", "of", "to", "in", "for",
            "with", "on", "at", "by", "about", "find", "show",
            "tell", "me", "all", "any", "some",
        }
        
        words = query.lower().replace("?", "").split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords
    
    def _merge_and_rank(
        self,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Merge and rank results from different sources."""
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Deduplicate by content similarity (simple approach)
        seen_content = set()
        unique_results = []
        
        for r in results:
            content_key = r.content[:100]  # First 100 chars as key
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    async def _generate_answer(
        self,
        query: str,
        results: list[SearchResult],
    ) -> str:
        """Generate answer from search results."""
        
        # Format results for prompt
        context_parts = []
        for i, r in enumerate(results[:5], 1):
            context_parts.append(f"{i}. [{r.source}] {r.content}")
        
        context = "\n".join(context_parts)
        
        prompt = f"""Based on the following search results, answer the user's question.
Cite specific results when possible using [source].

QUESTION: {query}

SEARCH RESULTS:
{context}

Provide a clear, concise answer based on the results above.
If the results don't contain relevant information, say so.
"""
        
        try:
            return await self.llm.complete(prompt, temperature=0.4)
        except Exception as e:
            return f"Could not generate answer: {str(e)}"


# Convenience function
async def hybrid_search(
    query: str,
    top_k: int = 10,
    generate_answer: bool = True,
) -> HybridSearchResult:
    """
    Perform hybrid RAG search.
    
    Convenience wrapper for HybridRAGAgent.
    """
    agent = HybridRAGAgent()
    return await agent.search(query, top_k, generate_answer=generate_answer)
