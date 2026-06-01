"""
Validate API Endpoint

Provides REST API for validating triples using MAKGED.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from validators.makged import MAKGEDValidator, Triple


router = APIRouter(prefix="/validate", tags=["Validation"])


class TripleInput(BaseModel):
    """Triple to validate."""
    subject: Optional[str] = Field(None, description="Subject/head entity")
    predicate: Optional[str] = Field(None, description="Predicate/relation")
    object: Optional[str] = Field(None, description="Object/tail entity")
    # Alternative naming
    head: Optional[str] = Field(None, description="Head entity (alias for subject)")
    relation: Optional[str] = Field(None, description="Relation (alias for predicate)")
    tail: Optional[str] = Field(None, description="Tail entity (alias for object)")


class ValidateRequestBody(BaseModel):
    """Request body for validation."""
    triple: TripleInput = Field(..., description="Triple to validate")
    context: str = Field(default="", description="Source text context")
    max_rounds: int = Field(default=3, description="Max discussion rounds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "triple": {
                    "subject": "Google",
                    "predicate": "COLLECTS",
                    "object": "Location Data"
                },
                "context": "Google collects your location data to provide personalized services."
            }
        }


class AgentVote(BaseModel):
    """Single agent's vote."""
    verdict: str
    confidence: float
    reasoning: str


class ValidateResponse(BaseModel):
    """Response from validation."""
    success: bool
    decision: str  # ACCEPT, REJECT, NEEDS_REVIEW
    votes: dict  # {"correct": n, "incorrect": m}
    rounds: int
    triple: dict
    cypher_statement: Optional[str] = None
    agent_responses: dict = {}


@router.post("", response_model=ValidateResponse)
async def validate_triple(body: ValidateRequestBody):
    """
    Validate a knowledge graph triple using MAKGED.
    
    MAKGED uses 4 parallel agents to analyze the triple from different
    perspectives and vote on its validity.
    
    - 4/4 consensus → immediate decision
    - 3/4 majority → decision  
    - 2/2 tie → NEEDS_REVIEW or iterate
    """
    # Build triple from input (support both naming conventions)
    triple = Triple(
        head=body.triple.subject or body.triple.head or "Unknown",
        relation=body.triple.predicate or body.triple.relation or "UNKNOWN",
        tail=body.triple.object or body.triple.tail or "Unknown",
    )
    
    validator = MAKGEDValidator(max_rounds=body.max_rounds)
    
    try:
        result = await validator.validate(
            triple=triple,
            source_text=body.context,
        )
        
        return ValidateResponse(
            success=result.success,
            decision=result.decision.value,
            votes=result.votes,
            rounds=result.rounds,
            triple={
                "head": result.triple.head,
                "relation": result.triple.relation,
                "tail": result.triple.tail,
            },
            cypher_statement=result.cypher_statement,
            agent_responses=result.agent_responses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def validate_triples_batch(triples: list[ValidateRequestBody]):
    """
    Validate multiple triples.
    
    Processes triples sequentially and returns all results.
    """
    results = []
    
    for body in triples:
        triple = Triple(
            head=body.triple.subject or body.triple.head or "Unknown",
            relation=body.triple.predicate or body.triple.relation or "UNKNOWN",
            tail=body.triple.object or body.triple.tail or "Unknown",
        )
        
        validator = MAKGEDValidator(max_rounds=body.max_rounds)
        
        try:
            result = await validator.validate(
                triple=triple,
                source_text=body.context,
            )
            results.append({
                "success": True,
                "decision": result.decision.value,
                "votes": result.votes,
                "triple": {
                    "head": result.triple.head,
                    "relation": result.triple.relation,
                    "tail": result.triple.tail,
                },
            })
        except Exception as e:
            results.append({
                "success": False,
                "error": str(e),
                "triple": {
                    "head": triple.head,
                    "relation": triple.relation,
                    "tail": triple.tail,
                },
            })
    
    return {"results": results, "total": len(results)}
