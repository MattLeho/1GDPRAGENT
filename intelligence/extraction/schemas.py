"""
Extraction Schemas

Pydantic models for all extraction types following strict typing patterns.
These schemas enforce data integrity and provide serialization for API responses.

Design Philosophy:
- Immutable data structures where possible
- Comprehensive validation with clear error messages
- JSON-compatible for Neo4j property storage
- Support for both SPO and grounded extraction paradigms
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# Enumerations
# =============================================================================

class ExtractionSource(str, Enum):
    """Source type for extracted data."""
    GDPR_PDF = "gdpr_pdf"
    ONSIT_CRAWL = "onsit_crawl"
    MANUAL_INPUT = "manual_input"
    INFERENCE = "inference"


class RiskLevel(str, Enum):
    """Risk classification for data exposure."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EntityClass(str, Enum):
    """LangExtract-style entity classes for GDPR domain."""
    DATA_COLLECTION = "data_collection"
    DATA_SHARING = "data_sharing"
    DATA_RIGHT = "data_right"
    THIRD_PARTY = "third_party"
    PERSONAL_DATA = "personal_data"
    LEGAL_BASIS = "legal_basis"
    RETENTION = "retention"


# =============================================================================
# Core Triple Schema (AI-KG Pattern)
# =============================================================================

class SPOTriple(BaseModel):
    """
    Subject-Predicate-Object triple following AI-KG extraction pattern.
    
    The fundamental unit of knowledge graph extraction. Each triple
    represents a relationship between two entities.
    
    Attributes:
        subject: The entity performing the action or holding the property
        predicate: The relationship type (normalized to UPPER_SNAKE_CASE)
        object: The target entity or value
        confidence: Extraction confidence score (0.0-1.0)
        source_chunk: Index of the source chunk (for provenance)
        source_text: Original text span (for grounding)
        inferred: Whether this triple was inferred vs directly extracted
    """
    
    model_config = ConfigDict(frozen=True)  # Immutable
    
    subject: str = Field(..., min_length=1, description="Source entity")
    predicate: str = Field(..., min_length=1, description="Relationship type")
    object: str = Field(..., min_length=1, description="Target entity")
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0,
        description="Extraction confidence"
    )
    source_chunk: Optional[int] = Field(
        default=None,
        description="Source chunk index for provenance"
    )
    source_text: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Original text span for grounding"
    )
    inferred: bool = Field(
        default=False,
        description="True if relationship was inferred, not directly extracted"
    )
    
    @field_validator("predicate")
    @classmethod
    def normalize_predicate(cls, v: str) -> str:
        """Normalize predicate to UPPER_SNAKE_CASE."""
        # Replace spaces and hyphens with underscores
        normalized = v.strip().upper().replace(" ", "_").replace("-", "_")
        # Remove consecutive underscores
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        return normalized
    
    def to_neo4j_props(self) -> dict[str, Any]:
        """Convert to Neo4j relationship properties."""
        return {
            "confidence": self.confidence,
            "source_chunk": self.source_chunk,
            "source_text": self.source_text,
            "inferred": self.inferred,
            "extracted_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Text Chunk Schema
# =============================================================================

class TextChunk(BaseModel):
    """
    Represents a chunk of text with offset tracking for source grounding.
    
    Following AI-KG chunking pattern with extensions for precise
    source mapping required by LangExtract.
    """
    
    text: str = Field(..., description="Chunk text content")
    start_offset: int = Field(..., ge=0, description="Start character offset")
    end_offset: int = Field(..., ge=0, description="End character offset")
    chunk_index: int = Field(..., ge=0, description="Sequential chunk number")
    word_count: int = Field(default=0, ge=0, description="Word count")
    
    @field_validator("end_offset")
    @classmethod
    def validate_offsets(cls, v: int, info) -> int:
        """Ensure end_offset >= start_offset."""
        start = info.data.get("start_offset", 0)
        if v < start:
            raise ValueError(f"end_offset ({v}) must be >= start_offset ({start})")
        return v
    
    def __len__(self) -> int:
        return len(self.text)


# =============================================================================
# Grounded Entity Schema (LangExtract Pattern)
# =============================================================================

class GroundedEntity(BaseModel):
    """
    Entity with source text grounding following LangExtract pattern.
    
    Unlike SPO triples which focus on relationships, grounded entities
    capture structured information with precise source attribution.
    """
    
    entity_class: EntityClass = Field(..., description="Extraction class")
    text: str = Field(..., description="Extracted text span")
    start_offset: int = Field(..., ge=0, description="Start position in source")
    end_offset: int = Field(..., ge=0, description="End position in source")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Schema-specific attributes"
    )
    source_document: Optional[str] = Field(
        default=None,
        description="Source document identifier"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    def to_neo4j_props(self) -> dict[str, Any]:
        """Convert to Neo4j node properties."""
        props = {
            "entity_class": self.entity_class.value,
            "text": self.text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": self.confidence,
            "source_document": self.source_document,
        }
        props.update(self.attributes)
        return props


# =============================================================================
# Validation Result Schema (MAKGED Pattern)
# =============================================================================

class ValidationResult(BaseModel):
    """
    Result of MAKGED multi-agent validation.
    
    Captures the debate outcome between forward and backward agents
    including confidence scores and rejection reasons.
    """
    
    triple: SPOTriple = Field(..., description="The validated triple")
    is_valid: bool = Field(..., description="Final validation verdict")
    forward_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Forward agent confidence"
    )
    backward_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Backward agent confidence"
    )
    judge_verdict: Optional[str] = Field(
        default=None,
        description="Tiebreaker judge decision if needed"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejection if invalid"
    )
    debate_rounds: int = Field(
        default=2,
        ge=1,
        description="Number of debate rounds conducted"
    )


# =============================================================================
# Extraction Result Schema
# =============================================================================

class ExtractionResult(BaseModel):
    """
    Complete extraction result from the pipeline.
    
    Aggregates all outputs from chunking, extraction, standardization,
    inference, and validation stages.
    """
    
    source_document: str = Field(..., description="Source document identifier")
    source_type: ExtractionSource = Field(
        default=ExtractionSource.GDPR_PDF,
        description="Type of source"
    )
    
    # Extracted data
    triples: list[SPOTriple] = Field(
        default_factory=list,
        description="Extracted SPO triples"
    )
    grounded_entities: list[GroundedEntity] = Field(
        default_factory=list,
        description="Grounded entity extractions"
    )
    
    # Graph analysis
    communities: list[list[str]] = Field(
        default_factory=list,
        description="Detected communities of entities"
    )
    community_count: int = Field(default=0, description="Number of communities")
    
    # Statistics
    chunk_count: int = Field(default=0, description="Number of chunks processed")
    triple_count: int = Field(default=0, description="Total triples extracted")
    inferred_count: int = Field(default=0, description="Triples from inference")
    validated_count: int = Field(default=0, description="Triples that passed validation")
    rejected_count: int = Field(default=0, description="Triples that failed validation")
    
    # Metadata
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Processing timestamp"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Total processing time in milliseconds"
    )
    
    def compute_stats(self) -> None:
        """Recompute statistics from data."""
        self.triple_count = len(self.triples)
        self.inferred_count = sum(1 for t in self.triples if t.inferred)
        self.community_count = len(self.communities)


# =============================================================================
# Configuration Schemas
# =============================================================================

class ChunkingConfig(BaseModel):
    """Configuration for text chunking."""
    
    chunk_size: int = Field(default=500, ge=50, le=2000)
    overlap: int = Field(default=50, ge=0, le=500)
    preserve_sentences: bool = Field(default=True)
    max_chunk_size: int = Field(default=1000, ge=100)


class InferenceConfig(BaseModel):
    """Configuration for relationship inference."""
    
    use_llm_for_inference: bool = Field(default=True)
    apply_transitive: bool = Field(default=True)
    use_lexical_similarity: bool = Field(default=True)
    max_predicate_words: int = Field(default=3, ge=1, le=5)
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class PipelineConfig(BaseModel):
    """Full pipeline configuration."""
    
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    
    # Extraction settings
    extraction_passes: int = Field(default=1, ge=1, le=5)
    use_grounded_extraction: bool = Field(default=True)
    use_spo_extraction: bool = Field(default=True)
    
    # Validation settings
    enable_standardization: bool = Field(default=True)
    enable_inference: bool = Field(default=True)
    enable_validation: bool = Field(default=True)
    
    # Performance
    max_workers: int = Field(default=10, ge=1, le=50)
    batch_size: int = Field(default=10, ge=1, le=100)
