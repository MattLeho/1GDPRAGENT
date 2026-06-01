"""
FastAPI Server for GDPR Agent

Provides HTTP endpoints for the GDPR request drafting agent.
Called from the Next.js frontend via internal API calls.
"""

import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import uvicorn

from gdpr_agent import GDPRRequestDrafter, create_agent, PolicyAnalysis


# =============================================================================
# Request/Response Models
# =============================================================================

class DraftRequestBody(BaseModel):
    """Request body for drafting a GDPR request."""
    request_type: str  # access, erasure, rectification, portability, objection
    company: str
    user_query: str
    user_name: str
    user_email: EmailStr
    policy_url: Optional[str] = None
    api_key: Optional[str] = None  # Optional override


class DraftRequestResponse(BaseModel):
    """Response for a drafted request."""
    success: bool
    request_type: str
    company: str
    subject: str
    body: str
    articles_cited: list[int]
    deadline_days: int


class AnalyzePolicyBody(BaseModel):
    """Request body for analyzing a privacy policy."""
    policy_text: str
    company: str
    api_key: Optional[str] = None


class AnalyzePolicyResponse(BaseModel):
    """Response for policy analysis."""
    success: bool
    company: str
    compliance_score: float
    findings: list[str]
    data_categories: list[str]
    recommendations: list[str]


class SearchArticlesBody(BaseModel):
    """Request body for searching GDPR articles."""
    query: str
    api_key: Optional[str] = None


class SearchArticlesResponse(BaseModel):
    """Response for article search."""
    success: bool
    articles: list[int]
    article_content: dict[str, str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    gdpr_loaded: bool
    gdpr_sections: int


# =============================================================================
# Application Lifespan
# =============================================================================

# Global agent instance
_agent: Optional[GDPRRequestDrafter] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup."""
    global _agent
    try:
        _agent = create_agent()
        print("[Server] GDPR Agent initialized successfully")
    except Exception as e:
        print(f"[Server] Warning: Could not initialize agent: {e}")
        _agent = None
    yield
    # Cleanup
    _agent = None


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="GDPR Request Agent",
    description="RLM-based agent for drafting GDPR data requests",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_agent(api_key: Optional[str] = None) -> GDPRRequestDrafter:
    """Get or create an agent instance."""
    global _agent
    if api_key:
        # Create new agent with provided key
        return create_agent(api_key)
    if _agent is None:
        _agent = create_agent()
    return _agent


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health and GDPR load status."""
    global _agent
    if _agent and _agent.gdpr_context:
        return HealthResponse(
            status="healthy",
            gdpr_loaded=True,
            gdpr_sections=len(_agent.gdpr_context.sections)
        )
    return HealthResponse(
        status="degraded",
        gdpr_loaded=False,
        gdpr_sections=0
    )


@app.post("/draft-request", response_model=DraftRequestResponse)
async def draft_request(body: DraftRequestBody):
    """
    Draft a GDPR request using the RLM agent.
    
    1. Searches GDPR for relevant articles
    2. Synthesizes formal request letter
    3. Returns ready-to-send draft
    """
    try:
        agent = get_agent(body.api_key)
        
        draft = await agent.draft_request(
            request_type=body.request_type,
            company=body.company,
            user_query=body.user_query,
            user_name=body.user_name,
            user_email=body.user_email,
            policy_url=body.policy_url
        )
        
        return DraftRequestResponse(
            success=True,
            request_type=draft.request_type,
            company=draft.company,
            subject=draft.subject,
            body=draft.body,
            articles_cited=draft.articles_cited,
            deadline_days=draft.deadline_days
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-policy", response_model=AnalyzePolicyResponse)
async def analyze_policy(body: AnalyzePolicyBody):
    """
    Analyze a privacy policy for GDPR compliance.
    
    Uses recursive chunking for long policies.
    """
    try:
        agent = get_agent(body.api_key)
        
        analysis = await agent.analyze_policy(
            policy_text=body.policy_text,
            company=body.company
        )
        
        return AnalyzePolicyResponse(
            success=True,
            company=analysis.company,
            compliance_score=analysis.compliance_score,
            findings=analysis.findings,
            data_categories=analysis.data_categories,
            recommendations=analysis.recommendations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search-articles", response_model=SearchArticlesResponse)
async def search_articles(body: SearchArticlesBody):
    """
    Search GDPR for relevant articles based on a query.
    
    Returns article numbers and content snippets.
    """
    try:
        agent = get_agent(body.api_key)
        
        articles = await agent.find_relevant_articles(body.query)
        article_content = await agent.get_article_content(articles)
        
        # Truncate content for response
        truncated_content = {
            str(num): content[:1000] + "..." if len(content) > 1000 else content
            for num, content in article_content.items()
        }
        
        return SearchArticlesResponse(
            success=True,
            articles=articles,
            article_content=truncated_content
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("GDPR_AGENT_PORT", "8000"))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
