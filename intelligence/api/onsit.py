"""
ONSIT API Endpoints

FastAPI routes for ONSIT discovery functionality.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from onsit import (
    ONSITEntity,
    EntityType,
    ScanStatus,
    CrawlResult,
    ONSITCrawler,
    CrawlerConfig,
    quick_crawl,
)
from onsit.orchestrator import default_orchestrator
from onsit.enrichers import default_registry


router = APIRouter(prefix="/onsit", tags=["ONSIT Discovery"])


# =============================================================================
# Request/Response Models
# =============================================================================

class DiscoverRequest(BaseModel):
    """Request to start a discovery scan."""
    seeds: list[str] = Field(
        ..., 
        description="List of seeds (emails, domains, usernames)",
        min_length=1,
        max_length=50,
    )
    enrichers: Optional[list[str]] = Field(
        None,
        description="Specific enrichers to use (None = all applicable)"
    )


class DiscoverResponse(BaseModel):
    """Response from starting a discovery scan."""
    scan_id: str
    status: str
    message: str


class CrawlRequest(BaseModel):
    """Request to crawl a URL."""
    url: str = Field(..., description="URL to crawl")
    max_depth: int = Field(2, ge=1, le=5)
    max_pages: int = Field(50, ge=1, le=200)


class EnrichRequest(BaseModel):
    """Request to enrich an entity."""
    entity_type: str = Field(..., description="Entity type (email, domain, username)")
    value: str = Field(..., description="Entity value")
    enrichers: Optional[list[str]] = None


class EntityResponse(BaseModel):
    """Generic entity response."""
    entity_type: str
    label: str
    value: dict
    source: Optional[str]
    discovered_at: datetime


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/discover", response_model=DiscoverResponse)
async def start_discovery(request: DiscoverRequest):
    """
    Start an ONSIT discovery scan.
    
    Seeds can be:
    - Email addresses (user@example.com)
    - Domain names (example.com)
    - Usernames (@username or just username)
    - URLs (https://example.com)
    
    The scan runs asynchronously. Use GET /discover/{scan_id} to check status.
    """
    try:
        scan_id = await default_orchestrator.start_discovery(
            seeds=request.seeds,
            enrichers=request.enrichers,
        )
        
        return DiscoverResponse(
            scan_id=scan_id,
            status="started",
            message=f"Discovery scan started with {len(request.seeds)} seed(s)"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {e}")


@router.get("/discover/{scan_id}", response_model=ScanStatus)
async def get_scan_status(scan_id: str):
    """
    Get the status of a discovery scan.
    """
    status = await default_orchestrator.get_status(scan_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return status


@router.get("/discover/{scan_id}/findings")
async def get_scan_findings(
    scan_id: str,
    entity_type: Optional[str] = None,
    limit: int = 100,
):
    """
    Get findings from a discovery scan.
    
    Optionally filter by entity type and limit results.
    """
    # Parse entity type if provided
    filter_type = None
    if entity_type:
        try:
            filter_type = EntityType(entity_type)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid entity type: {entity_type}"
            )
    
    findings = await default_orchestrator.get_findings(
        scan_id=scan_id,
        entity_type=filter_type,
        limit=min(limit, 500),
    )
    
    return {
        "scan_id": scan_id,
        "count": len(findings),
        "findings": [
            {
                "type": f.entity_type.value,
                "label": f.label,
                "data": f.model_dump(exclude={"metadata"}),
                "source": f.source,
            }
            for f in findings
        ]
    }


@router.delete("/discover/{scan_id}")
async def cancel_scan(scan_id: str):
    """
    Cancel a running discovery scan.
    """
    cancelled = await default_orchestrator.cancel_scan(scan_id)
    
    if cancelled:
        return {"status": "cancelled", "scan_id": scan_id}
    else:
        raise HTTPException(
            status_code=400, 
            detail="Scan not found or already completed"
        )


@router.post("/crawl")
async def crawl_url(request: CrawlRequest):
    """
    Crawl a single URL and extract intel.
    
    Returns URLs, scripts, and intelligence findings.
    """
    try:
        config = CrawlerConfig(
            max_depth=request.max_depth,
            max_pages=request.max_pages,
        )
        crawler = ONSITCrawler(config)
        result = await crawler.crawl(request.url)
        
        return {
            "url": result.url,
            "status_code": result.status_code,
            "internal_urls": len(result.internal_urls),
            "external_urls": len(result.external_urls),
            "scripts": len(result.scripts),
            "files": len(result.files),
            "intel_count": len(result.intel),
            "intel": [
                {
                    "type": f.finding_type.value,
                    "value": f.value,
                    "risk": f.risk_level,
                }
                for f in result.intel[:50]  # Limit response
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {e}")


@router.post("/enrich")
async def enrich_entity(request: EnrichRequest):
    """
    Enrich a single entity using specified enrichers.
    """
    from onsit import Email, Domain, Username
    
    # Create entity based on type
    entity = None
    try:
        if request.entity_type == "email":
            entity = Email(email=request.value)
        elif request.entity_type == "domain":
            entity = Domain(domain=request.value)
        elif request.entity_type == "username":
            entity = Username(username=request.value)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported entity type: {request.entity_type}"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Run enrichers
    results = await default_registry.enrich_entity(
        entity,
        request.enrichers
    )
    
    return {
        "input": {
            "type": request.entity_type,
            "value": request.value,
        },
        "results_count": len(results),
        "results": [
            {
                "type": r.entity_type.value,
                "label": r.label,
                "data": r.model_dump(exclude={"metadata"}),
                "source": r.source,
            }
            for r in results
        ]
    }


@router.get("/enrichers")
async def list_enrichers():
    """
    List all available enrichers.
    """
    enrichers = default_registry.all()
    
    return {
        "count": len(enrichers),
        "enrichers": [
            {
                "name": e.name,
                "input_type": e.input_type.value if e.input_type else None,
                "output_types": [t.value for t in e.output_types],
                "requires_api_key": e.requires_api_key,
                "rate_limit": e.rate_limit,
            }
            for e in enrichers
        ]
    }
