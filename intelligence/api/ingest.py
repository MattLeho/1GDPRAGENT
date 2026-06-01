"""
Ingest API Endpoint

Provides REST API for ingesting data into the knowledge graph.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from agents.kg_ingestor import KGIngestorAgent, IngestRequest


router = APIRouter(prefix="/ingest", tags=["Ingestion"])


class IngestRequestBody(BaseModel):
    """Request body for ingestion."""
    company_name: str = Field(..., description="Name of the company")
    request_id: Optional[str] = Field(None, description="UUID of the associated request")
    extracted_data: list[dict] = Field(default_factory=list, description="Extracted entities")
    categories: dict = Field(default_factory=dict, description="Categorized data")
    source: str = Field(default="manual", description="Data source")
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Google",
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "categories": {
                    "CONTACT_INFO": {
                        "examples": ["user@gmail.com"],
                        "riskLevel": "MEDIUM"
                    }
                },
                "extracted_data": [
                    {"type": "email", "value": "user@gmail.com", "category": "CONTACT_INFO"}
                ]
            }
        }


class IngestResponse(BaseModel):
    """Response from ingestion."""
    success: bool
    request_id: str
    company_name: str
    total_items: int
    statements_executed: int
    statements_errored: int
    errors: list[str] = []


class IngestAsyncResponse(BaseModel):
    """Response for async ingestion."""
    status: str = "queued"
    task_id: str
    request_id: str


@router.post("", response_model=IngestResponse)
async def ingest_data(body: IngestRequestBody):
    """
    Ingest extracted data into the knowledge graph.
    
    This endpoint processes the data synchronously and returns the result.
    For large datasets, use the async endpoint.
    """
    # Generate request_id if not provided
    request_id = body.request_id or str(uuid.uuid4())
    
    agent = KGIngestorAgent()
    request = IngestRequest(
        company_name=body.company_name,
        request_id=request_id,
        extracted_data=body.extracted_data,
        categories=body.categories,
        source=body.source,
    )
    
    try:
        result = await agent.ingest(request)
        return IngestResponse(
            success=result.success,
            request_id=result.request_id,
            company_name=result.company_name,
            total_items=result.total_items,
            statements_executed=result.statements_executed,
            statements_errored=result.statements_errored,
            errors=result.errors,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/async", response_model=IngestAsyncResponse)
async def ingest_data_async(
    body: IngestRequestBody,
    background_tasks: BackgroundTasks,
):
    """
    Queue data ingestion as a background task.
    
    Returns immediately with a task ID. Check progress via the messages table.
    """
    from tasks import app as celery_app
    
    request_id = body.request_id or str(uuid.uuid4())
    
    # Queue Celery task
    task = celery_app.send_task(
        "intelligence.ingest_to_graph",
        args=[{
            "company_name": body.company_name,
            "request_id": request_id,
            "extracted_data": body.extracted_data,
            "categories": body.categories,
            "source": body.source,
        }],
    )
    
    return IngestAsyncResponse(
        status="queued",
        task_id=task.id,
        request_id=request_id,
    )
