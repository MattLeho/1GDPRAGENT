"""
Intelligence Service - FastAPI Application

Main entry point for the Python intelligence layer.
Provides REST API endpoints for ONSIT discovery, graph extraction, and validation.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from api.health import router as health_router
from api.ingest import router as ingest_router
from api.validate import router as validate_router
from api.query import router as query_router
from api.onsit import router as onsit_router
from api.extract import router as extract_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print(f"[{settings.service_name}] Starting up...")
    print(f"[{settings.service_name}] Gemini API configured: {'Yes' if settings.google_api_key else 'No'}")
    print(f"[{settings.service_name}] Redis URL: {settings.redis_url}")
    
    yield
    
    # Shutdown
    print(f"[{settings.service_name}] Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="GDPR Intelligence Service",
    description="Python intelligence layer for ONSIT discovery and graph processing",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://nextjs_app:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(ingest_router, tags=["Ingestion"])
app.include_router(validate_router, tags=["Validation"])
app.include_router(query_router, tags=["Query"])
app.include_router(onsit_router, tags=["ONSIT Discovery"])
app.include_router(extract_router, tags=["File Extraction"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
