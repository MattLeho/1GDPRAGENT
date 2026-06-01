"""
Health Check Endpoints

Provides health and readiness endpoints for the intelligence service.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import redis

from config import get_settings


router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    status: str
    service: str
    checks: dict


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns OK if the service is running.
    """
    return HealthResponse(
        status="ok",
        service=settings.service_name,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check with dependency verification.
    
    Checks connections to Redis, and reports Gemini API status.
    """
    checks = {}
    overall_status = "ok"
    
    # Check Redis connection
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        overall_status = "degraded"
    
    # Check Gemini API key presence
    if settings.google_api_key:
        checks["gemini"] = "configured"
    else:
        checks["gemini"] = "not configured"
        overall_status = "degraded"
    
    return ReadinessResponse(
        status=overall_status,
        service=settings.service_name,
        checks=checks,
    )
