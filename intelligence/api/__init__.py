"""API package for Intelligence Service."""

from .health import router as health_router
from .ingest import router as ingest_router
from .validate import router as validate_router
from .query import router as query_router

__all__ = [
    "health_router",
    "ingest_router",
    "validate_router",
    "query_router",
]
