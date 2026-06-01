"""Agents package for Intelligence Service."""

from .kg_ingestor import KGIngestorAgent, ingest_to_graph, IngestRequest, IngestResult
from .shadow_oracle import ShadowOracleAgent, shadow_query, QueryResult
from .hybrid_rag import HybridRAGAgent, hybrid_search, HybridSearchResult

__all__ = [
    "KGIngestorAgent",
    "ingest_to_graph",
    "IngestRequest",
    "IngestResult",
    "ShadowOracleAgent",
    "shadow_query",
    "QueryResult",
    "HybridRAGAgent",
    "hybrid_search",
    "HybridSearchResult",
]
