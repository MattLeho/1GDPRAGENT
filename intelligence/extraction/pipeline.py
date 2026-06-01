"""
Extraction Pipeline Orchestration

Full end-to-end extraction pipeline following AI-KG main.py pattern.
Coordinates all stages: chunking, extraction, standardization, inference, validation, storage.

Key Features:
- Configurable stage enabling/disabling
- Progress callbacks for UI integration
- Batch document processing
- Both SPO and grounded extraction support
- Time tracking for performance monitoring
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Callable, Any
from datetime import datetime
from pathlib import Path

from .schemas import (
    SPOTriple,
    TextChunk,
    GroundedEntity,
    ExtractionResult,
    ExtractionSource,
    PipelineConfig,
    InferenceConfig,
)
from .chunker import chunk_document, chunk_text_with_offsets
from .spo_extractor import SPOExtractor
from .entity_resolver import EntityResolver
from .inference_engine import InferenceEngine
from .grounded_extractor import GroundedExtractor


# =============================================================================
# Pipeline Class
# =============================================================================

class ExtractionPipeline:
    """
    Orchestrates the complete extraction pipeline.
    
    Coordinates:
    1. Text chunking with overlap
    2. SPO triple extraction 
    3. Grounded entity extraction (optional)
    4. Entity standardization
    5. Relationship inference
    6. MAKGED validation (optional)
    
    Usage:
        pipeline = ExtractionPipeline(gemini_client, config)
        result = await pipeline.process_document(text, source="gdpr.pdf")
    """
    
    def __init__(
        self,
        gemini_client,
        config: Optional[PipelineConfig] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initialize extraction pipeline.
        
        Args:
            gemini_client: GeminiClient instance
            config: Pipeline configuration
            progress_callback: Optional callback(stage, progress) for UI updates
        """
        self.client = gemini_client
        self.config = config or PipelineConfig()
        self.progress_callback = progress_callback
        
        # Initialize sub-components
        self.spo_extractor = SPOExtractor(gemini_client)
        self.entity_resolver = EntityResolver(gemini_client)
        self.inference_engine = InferenceEngine(gemini_client)
        self.grounded_extractor = GroundedExtractor(gemini_client)
    
    async def process_document(
        self,
        text: str,
        source: str,
        source_type: ExtractionSource = ExtractionSource.GDPR_PDF,
    ) -> ExtractionResult:
        """
        Process a single document through the full pipeline.
        
        Args:
            text: Document text content
            source: Source document identifier
            source_type: Type of source document
            
        Returns:
            ExtractionResult with all extracted data
        """
        start_time = time.time()
        
        result = ExtractionResult(
            source_document=source,
            source_type=source_type,
        )
        
        # Stage 1: Chunking
        self._report_progress("chunking", 0.0)
        chunks = await self._stage_chunk(text)
        result.chunk_count = len(chunks)
        self._report_progress("chunking", 1.0)
        
        # Stage 2: SPO Extraction
        triples = []
        if self.config.use_spo_extraction:
            self._report_progress("spo_extraction", 0.0)
            triples = await self._stage_extract(chunks)
            self._report_progress("spo_extraction", 1.0)
        
        # Stage 3: Grounded Extraction
        grounded_entities = []
        if self.config.use_grounded_extraction:
            self._report_progress("grounded_extraction", 0.0)
            grounded_entities = await self._stage_ground(text, source)
            self._report_progress("grounded_extraction", 1.0)
        
        # Stage 4: Entity Standardization
        if self.config.enable_standardization and triples:
            self._report_progress("standardization", 0.0)
            triples = await self._stage_standardize(triples)
            self._report_progress("standardization", 1.0)
        
        # Stage 5: Relationship Inference
        if self.config.enable_inference and triples:
            self._report_progress("inference", 0.0)
            inference_config = self.config.inference
            original_count = len(triples)
            triples = await self._stage_infer(triples, inference_config)
            result.inferred_count = len(triples) - original_count
            self._report_progress("inference", 1.0)
        
        # Stage 6: Validation (if enabled)
        if self.config.enable_validation and triples:
            self._report_progress("validation", 0.0)
            validated, rejected = await self._stage_validate(triples, text)
            triples = validated
            result.validated_count = len(validated)
            result.rejected_count = rejected
            self._report_progress("validation", 1.0)
        
        # Detect communities for result
        if triples:
            communities = self.inference_engine._identify_communities(
                self.inference_engine._build_graph(triples)
            )
            result.communities = [list(c) for c in communities]
        
        # Finalize result
        result.triples = triples
        result.grounded_entities = grounded_entities
        result.compute_stats()
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        self._report_progress("complete", 1.0)
        
        return result
    
    async def process_batch(
        self,
        documents: list[tuple[str, str]],  # List of (text, source) tuples
        max_concurrent: int = 3,
    ) -> list[ExtractionResult]:
        """
        Process multiple documents with controlled concurrency.
        
        Args:
            documents: List of (text, source) tuples
            max_concurrent: Maximum concurrent document processing
            
        Returns:
            List of ExtractionResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_one(text: str, source: str) -> ExtractionResult:
            async with semaphore:
                return await self.process_document(text, source)
        
        tasks = [
            process_one(text, source)
            for text, source in documents
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        return [r for r in results if isinstance(r, ExtractionResult)]
    
    # =========================================================================
    # Pipeline Stages
    # =========================================================================
    
    async def _stage_chunk(
        self,
        text: str,
    ) -> list[TextChunk]:
        """Stage 1: Chunk document."""
        return chunk_document(
            text,
            config=self.config.chunking,
            preserve_sentences=self.config.chunking.preserve_sentences,
        )
    
    async def _stage_extract(
        self,
        chunks: list[TextChunk],
    ) -> list[SPOTriple]:
        """Stage 2: Extract SPO triples from chunks."""
        return await self.spo_extractor.extract_from_chunks(
            chunks,
            max_concurrent=self.config.max_workers,
        )
    
    async def _stage_ground(
        self,
        text: str,
        source: str,
    ) -> list[GroundedEntity]:
        """Stage 3: Extract grounded entities."""
        return await self.grounded_extractor.extract(
            text,
            source_document=source,
        )
    
    async def _stage_standardize(
        self,
        triples: list[SPOTriple],
    ) -> list[SPOTriple]:
        """Stage 4: Standardize entity names."""
        return await self.entity_resolver.standardize_entities(
            triples,
            use_llm=self.config.inference.use_llm_for_inference,
        )
    
    async def _stage_infer(
        self,
        triples: list[SPOTriple],
        config: InferenceConfig,
    ) -> list[SPOTriple]:
        """Stage 5: Infer additional relationships."""
        return await self.inference_engine.infer_relationships(triples, config)
    
    async def _stage_validate(
        self,
        triples: list[SPOTriple],
        context: str,
    ) -> tuple[list[SPOTriple], int]:
        """
        Stage 6: Validate triples with MAKGED.
        
        Returns tuple of (validated_triples, rejected_count).
        """
        # Simple validation: filter low-confidence inferred triples
        # Full MAKGED implementation would use multi-agent debate
        
        validated = []
        rejected = 0
        
        for triple in triples:
            # Keep all original triples
            if not triple.inferred:
                validated.append(triple)
            # Filter low-confidence inferred triples
            elif triple.confidence >= 0.5:
                validated.append(triple)
            else:
                rejected += 1
        
        return validated, rejected
    
    def _report_progress(self, stage: str, progress: float) -> None:
        """Report progress to callback if provided."""
        if self.progress_callback:
            try:
                self.progress_callback(stage, progress)
            except Exception:
                pass  # Don't let callback errors break pipeline


# =============================================================================
# Convenience Functions
# =============================================================================

async def extract_knowledge(
    text: str,
    gemini_client,
    source: str = "document",
    config: Optional[PipelineConfig] = None,
) -> ExtractionResult:
    """
    Quick extraction with default pipeline.
    
    Args:
        text: Document text
        gemini_client: GeminiClient instance
        source: Source identifier
        config: Optional configuration
        
    Returns:
        ExtractionResult
    """
    pipeline = ExtractionPipeline(gemini_client, config)
    return await pipeline.process_document(text, source)


async def extract_from_file(
    file_path: str | Path,
    gemini_client,
    config: Optional[PipelineConfig] = None,
) -> ExtractionResult:
    """
    Extract from a text file.
    
    Args:
        file_path: Path to text file
        gemini_client: GeminiClient instance
        config: Optional configuration
        
    Returns:
        ExtractionResult
    """
    path = Path(file_path)
    text = path.read_text(encoding='utf-8')
    source = path.name
    
    pipeline = ExtractionPipeline(gemini_client, config)
    return await pipeline.process_document(text, source)
