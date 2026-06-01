"""
Query API Endpoint

Provides REST API for querying the knowledge graph.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from agents.shadow_oracle import ShadowOracleAgent
from agents.hybrid_rag import HybridRAGAgent


router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequestBody(BaseModel):
    """Request body for query."""
    question: str = Field(..., description="Natural language question")
    user_id: str = Field(default="root", description="User ID for context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Who has my email address?",
                "user_id": "root"
            }
        }


class QueryResponse(BaseModel):
    """Response from query."""
    question: str
    answer: str
    evidence: list[dict] = []
    confidence: float = 0.0


class SearchRequestBody(BaseModel):
    """Request body for hybrid search."""
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=10, description="Number of results")
    include_graph: bool = Field(default=True, description="Include graph results")
    include_vectors: bool = Field(default=True, description="Include vector results")
    generate_answer: bool = Field(default=True, description="Generate LLM answer")


class SearchResult(BaseModel):
    """Single search result."""
    content: str
    source: str
    score: float
    metadata: dict = {}


class SearchResponse(BaseModel):
    """Response from search."""
    query: str
    results: list[SearchResult]
    vector_count: int
    graph_count: int
    generated_answer: Optional[str] = None


@router.post("", response_model=QueryResponse)
async def query_graph(body: QueryRequestBody):
    """
    Query the knowledge graph using natural language.
    
    Uses the Shadow Oracle agent to retrieve relevant data and
    generate a privacy-focused answer.
    """
    agent = ShadowOracleAgent()
    
    try:
        result = await agent.query(
            question=body.question,
            user_id=body.user_id,
        )
        
        return QueryResponse(
            question=result.question,
            answer=result.answer,
            evidence=result.evidence,
            confidence=result.confidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(body: SearchRequestBody):
    """
    Perform hybrid RAG search.
    
    Combines vector search (Qdrant) with graph traversal (Neo4j)
    for comprehensive results.
    """
    agent = HybridRAGAgent()
    
    try:
        result = await agent.search(
            query=body.query,
            top_k=body.top_k,
            include_graph=body.include_graph,
            include_vectors=body.include_vectors,
            generate_answer=body.generate_answer,
        )
        
        return SearchResponse(
            query=result.query,
            results=[
                SearchResult(
                    content=r.content,
                    source=r.source,
                    score=r.score,
                    metadata=r.metadata,
                )
                for r in result.results
            ],
            vector_count=result.vector_count,
            graph_count=result.graph_count,
            generated_answer=result.generated_answer,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
