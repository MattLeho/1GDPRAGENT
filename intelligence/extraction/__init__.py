"""
Extraction Engine Package

Provides comprehensive knowledge extraction capabilities:
- Text chunking with overlap for LLM context
- SPO triple extraction using Gemini
- Entity standardization and resolution
- Relationship inference (transitive, community-based, LLM-assisted)
- Grounded extraction with source mapping
- Graph visualization and storage

Source patterns:
- AI-KG: https://github.com/robert-mcdermott/ai-knowledge-graph
- LangExtract: https://github.com/google/langextract
"""

# Schemas
from .schemas import (
    SPOTriple,
    TextChunk,
    GroundedEntity,
    ExtractionResult,
    ValidationResult,
    ExtractionSource,
    RiskLevel,
    EntityClass,
    ChunkingConfig,
    InferenceConfig,
    PipelineConfig,
)

# Chunker
from .chunker import (
    chunk_text,
    chunk_text_with_offsets,
    chunk_document,
    chunk_with_token_limit,
    estimate_chunk_count,
    get_chunk_context,
)

# SPO Extractor
from .spo_extractor import (
    SPOExtractor,
    extract_spo_triples,
    normalize_predicate,
)

# Entity Resolver
from .entity_resolver import (
    EntityResolver,
    standardize_entities,
    resolve_entity_variants,
)

# Inference Engine
from .inference_engine import (
    InferenceEngine,
    infer_relationships,
)

# Grounded Extractor
from .grounded_extractor import (
    GroundedExtractor,
    ExampleData,
    ExampleExtraction,
    ExtractionTask,
    extract_grounded,
    GDPR_EXTRACTION_SCHEMA,
)

# Storage
from .storage import (
    ExtractionStorage,
    get_entity_relationships,
    get_graph_data,
)

# Visualizer
from .visualizer import (
    GraphVisualizer,
    generate_graph_html,
)

# Context Restorer (TCR-QF Academic Pattern)
from .context_restorer import (
    TripleContextRestorer,
    ContextualTriple,
    MissingKnowledge,
    restore_triple_context,
    find_knowledge_gaps,
)

# Veracity Extrapolator (GIVE Academic Pattern)
from .veracity_extrapolator import (
    VeracityExtrapolator,
    EntityGroup,
    ExtrapolatedEdge,
    ReasoningChain,
    extrapolate_relations,
    find_reasoning_path,
)

# Pipeline
from .pipeline import (
    ExtractionPipeline,
    extract_knowledge,
    extract_from_file,
)

__all__ = [
    # Schemas
    "SPOTriple",
    "TextChunk",
    "GroundedEntity",
    "ExtractionResult",
    "ValidationResult",
    "ExtractionSource",
    "RiskLevel",
    "EntityClass",
    "ChunkingConfig",
    "InferenceConfig",
    "PipelineConfig",
    # Chunker
    "chunk_text",
    "chunk_text_with_offsets",
    "chunk_document",
    "chunk_with_token_limit",
    "estimate_chunk_count",
    "get_chunk_context",
    # SPO Extractor
    "SPOExtractor",
    "extract_spo_triples",
    "normalize_predicate",
    # Entity Resolver
    "EntityResolver",
    "standardize_entities",
    "resolve_entity_variants",
    # Inference Engine
    "InferenceEngine",
    "infer_relationships",
    # Grounded Extractor
    "GroundedExtractor",
    "ExampleData",
    "ExampleExtraction",
    "ExtractionTask",
    "extract_grounded",
    "GDPR_EXTRACTION_SCHEMA",
    # Storage
    "ExtractionStorage",
    "get_entity_relationships",
    "get_graph_data",
    # Visualizer
    "GraphVisualizer",
    "generate_graph_html",
    # Context Restorer (TCR-QF)
    "TripleContextRestorer",
    "ContextualTriple",
    "MissingKnowledge",
    "restore_triple_context",
    "find_knowledge_gaps",
    # Veracity Extrapolator (GIVE)
    "VeracityExtrapolator",
    "EntityGroup",
    "ExtrapolatedEdge",
    "ReasoningChain",
    "extrapolate_relations",
    "find_reasoning_path",
    # Pipeline
    "ExtractionPipeline",
    "extract_knowledge",
    "extract_from_file",
]

