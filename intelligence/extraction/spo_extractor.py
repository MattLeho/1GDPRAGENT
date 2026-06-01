"""
SPO Triple Extraction using Gemini

Implements Subject-Predicate-Object extraction following AI-KG Phase 1 patterns.
Uses the google-genai SDK for structured JSON extraction with validation.

Key Features:
- Batch extraction from chunked documents
- Predicate normalization (max 3 words, stopword cleanup)
- Confidence scoring per triple
- JSON extraction with error recovery
- Source chunk linking for provenance

Source patterns: https://github.com/robert-mcdermott/ai-knowledge-graph
"""

from __future__ import annotations

import json
import re
import asyncio
from typing import Optional
from dataclasses import dataclass

from .schemas import SPOTriple, TextChunk
from .chunker import chunk_text_with_offsets, ChunkingConfig


# =============================================================================
# Constants
# =============================================================================

# Stopwords to remove from predicate endings (from AI-KG)
PREDICATE_STOP_WORDS = frozenset({
    'a', 'an', 'the', 'of', 'with', 'by', 'to', 'from', 'in', 'on', 'for'
})

# JSON extraction patterns (from AI-KG llm.py)
CODE_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*([\s\S]*?)```')
JSON_ARRAY_START = re.compile(r'\[')

# GDPR-specific predicates to prioritize
GDPR_PREDICATES = frozenset({
    "COLLECTS", "SHARES_WITH", "STORES", "PROCESSES", "TRANSFERS_TO",
    "HAS_ACCESS_TO", "RETAINS", "DELETES_AFTER", "REQUIRES_CONSENT_FOR",
    "PROVIDES_RIGHT_TO", "THIRD_PARTY_ACCESS", "LEGAL_BASIS_FOR"
})


# =============================================================================
# SPO Extractor Class
# =============================================================================

class SPOExtractor:
    """
    Extracts Subject-Predicate-Object triples from text using Gemini.
    
    Follows AI-KG Phase 1 extraction pattern with enhancements for:
    - GDPR-specific relationship types
    - Confidence scoring
    - Source grounding via chunk indices
    
    Usage:
        extractor = SPOExtractor(gemini_client)
        triples = await extractor.extract_from_text("Google collects your location...")
    """
    
    def __init__(
        self,
        gemini_client,  # GeminiClient from llm/gemini.py
        max_predicates_per_chunk: int = 20,
        temperature: float = 0.2,
    ):
        """
        Initialize SPO extractor.
        
        Args:
            gemini_client: Configured GeminiClient instance
            max_predicates_per_chunk: Limit extractions per chunk to prevent hallucination
            temperature: LLM temperature (lower = more deterministic)
        """
        self.client = gemini_client
        self.max_predicates_per_chunk = max_predicates_per_chunk
        self.temperature = temperature
    
    async def extract_from_text(
        self,
        text: str,
        source_id: Optional[str] = None,
    ) -> list[SPOTriple]:
        """
        Extract SPO triples from a text string.
        
        Args:
            text: Input text to extract from
            source_id: Optional source identifier for provenance
            
        Returns:
            List of SPOTriple objects
        """
        # Chunk the text with offset tracking
        chunks = chunk_text_with_offsets(text)
        return await self.extract_from_chunks(chunks)
    
    async def extract_from_chunks(
        self,
        chunks: list[TextChunk],
        max_concurrent: int = 5,
    ) -> list[SPOTriple]:
        """
        Extract SPO triples from pre-chunked text.
        
        Processes chunks in parallel with rate limiting.
        
        Args:
            chunks: List of TextChunk objects
            max_concurrent: Maximum concurrent LLM calls
            
        Returns:
            Deduplicated list of SPOTriple objects
        """
        if not chunks:
            return []
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_chunk(chunk: TextChunk) -> list[SPOTriple]:
            async with semaphore:
                return await self._extract_single_chunk(chunk)
        
        # Process all chunks concurrently
        tasks = [extract_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and filter errors
        all_triples = []
        for result in results:
            if isinstance(result, Exception):
                # Log error but continue
                continue
            all_triples.extend(result)
        
        # Deduplicate triples
        return self._deduplicate_triples(all_triples)
    
    async def _extract_single_chunk(
        self,
        chunk: TextChunk,
    ) -> list[SPOTriple]:
        """
        Extract triples from a single chunk.
        
        Args:
            chunk: TextChunk to process
            
        Returns:
            List of SPOTriple objects with source_chunk set
        """
        prompt = self._build_extraction_prompt(chunk.text)
        
        try:
            # Use Gemini JSON extraction
            response = await self.client.extract_json(
                prompt=prompt,
                temperature=self.temperature,
            )
            
            # Handle both direct JSON and text response
            if isinstance(response, str):
                parsed = self._extract_json_from_text(response)
            else:
                parsed = response
            
            if not parsed:
                return []
            
            # Convert to SPOTriple objects
            triples = []
            items = parsed if isinstance(parsed, list) else [parsed]
            
            for item in items[:self.max_predicates_per_chunk]:
                if not self._validate_triple_dict(item):
                    continue
                
                triple = SPOTriple(
                    subject=str(item.get("subject", "")).strip(),
                    predicate=self._normalize_predicate(
                        str(item.get("predicate", "")),
                        max_words=3
                    ),
                    object=str(item.get("object", "")).strip(),
                    confidence=float(item.get("confidence", 0.8)),
                    source_chunk=chunk.chunk_index,
                    source_text=chunk.text[:200] if len(chunk.text) > 200 else chunk.text,
                    inferred=False,
                )
                triples.append(triple)
            
            return triples
            
        except Exception as e:
            # Return empty on error - errors will be logged at higher level
            return []
    
    def _build_extraction_prompt(self, text: str) -> str:
        """
        Build the SPO extraction prompt.
        
        Uses GDPR-focused instructions with examples.
        """
        return f"""You are a knowledge graph extraction expert specializing in GDPR and data privacy.

Extract ALL subject-predicate-object triples from this text. Focus on:
- Data collection (who collects what data)
- Data sharing (who shares data with whom)
- Data storage (where data is stored, for how long)
- Data processing (how data is used)
- User rights (what rights users have)
- Third parties (who has access to data)
- Legal basis (consent, legitimate interest, etc.)

For each triple, provide:
- subject: The entity performing the action (company, service, organization)
- predicate: The relationship type (use UPPERCASE_SNAKE_CASE, max 3 words)
- object: The target entity or data type
- confidence: Your confidence score (0.0-1.0)

Preferred predicates: COLLECTS, SHARES_WITH, STORES, PROCESSES, TRANSFERS_TO, HAS_ACCESS_TO, RETAINS, PROVIDES_RIGHT_TO, REQUIRES_CONSENT_FOR

TEXT:
{text}

Return a JSON array of triples. Example format:
[
  {{"subject": "Google", "predicate": "COLLECTS", "object": "location data", "confidence": 0.95}},
  {{"subject": "Google", "predicate": "SHARES_WITH", "object": "advertising partners", "confidence": 0.85}}
]"""
    
    def _normalize_predicate(
        self,
        predicate: str,
        max_words: int = 3,
    ) -> str:
        """
        Normalize predicate following AI-KG pattern.
        
        Enforces max word limit and removes trailing stopwords.
        """
        # Clean and uppercase
        predicate = predicate.strip().upper()
        predicate = predicate.replace(" ", "_").replace("-", "_")
        
        # Remove consecutive underscores
        while "__" in predicate:
            predicate = predicate.replace("__", "_")
        
        # Split into words
        words = predicate.split("_")
        
        if len(words) <= max_words:
            return "_".join(words)
        
        # Truncate to max_words
        shortened = words[:max_words]
        
        # Remove trailing stopwords
        while shortened and shortened[-1].lower() in PREDICATE_STOP_WORDS:
            shortened.pop()
        
        return "_".join(shortened) if shortened else "_".join(words[:max_words])
    
    def _extract_json_from_text(self, text: str) -> Optional[list]:
        """
        Extract JSON array from text, handling various formats.
        
        Direct port of AI-KG llm.py extract_json_from_text() pattern.
        """
        # Check for code blocks
        code_match = CODE_BLOCK_PATTERN.search(text)
        if code_match:
            text = code_match.group(1).strip()
        
        # Try direct parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Find JSON array bounds
        start_idx = text.find('[')
        if start_idx == -1:
            return None
        
        # Simple bracket counting
        bracket_count = 0
        for i in range(start_idx, len(text)):
            if text[i] == '[':
                bracket_count += 1
            elif text[i] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    json_str = text[start_idx:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        # Try fixing common issues
                        return self._fix_and_parse_json(json_str)
        
        return None
    
    def _fix_and_parse_json(self, json_str: str) -> Optional[list]:
        """
        Attempt to fix and parse malformed JSON.
        """
        # Fix missing quotes around keys
        fixed = re.sub(r'(\s*)(\w+)(\s*):(\s*)', r'\1"\2"\3:\4', json_str)
        # Fix trailing commas
        fixed = re.sub(r',(\s*[\]}])', r'\1', fixed)
        
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None
    
    def _validate_triple_dict(self, item: dict) -> bool:
        """
        Validate that a dict has required triple fields.
        """
        if not isinstance(item, dict):
            return False
        
        required = {"subject", "predicate", "object"}
        if not required.issubset(item.keys()):
            return False
        
        # Validate non-empty strings
        for field in required:
            value = item.get(field)
            if not value or not str(value).strip():
                return False
        
        return True
    
    def _deduplicate_triples(
        self,
        triples: list[SPOTriple],
    ) -> list[SPOTriple]:
        """
        Remove duplicate triples, keeping highest confidence version.
        
        Triples are considered duplicates if they have the same
        (subject, predicate, object) after normalization.
        """
        seen: dict[tuple, SPOTriple] = {}
        
        for triple in triples:
            key = (
                triple.subject.lower().strip(),
                triple.predicate.upper().strip(),
                triple.object.lower().strip(),
            )
            
            if key not in seen:
                seen[key] = triple
            elif triple.confidence > seen[key].confidence:
                # Keep higher confidence version
                seen[key] = triple
        
        return list(seen.values())


# =============================================================================
# Convenience Functions
# =============================================================================

async def extract_spo_triples(
    text: str,
    gemini_client,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[SPOTriple]:
    """
    Quick extraction using default settings.
    
    Args:
        text: Text to extract from
        gemini_client: GeminiClient instance
        chunk_size: Words per chunk
        overlap: Overlap words
        
    Returns:
        List of extracted SPOTriple objects
    """
    chunks = chunk_text_with_offsets(text, chunk_size=chunk_size, overlap=overlap)
    extractor = SPOExtractor(gemini_client)
    return await extractor.extract_from_chunks(chunks)


def normalize_predicate(predicate: str, max_words: int = 3) -> str:
    """
    Standalone predicate normalization function.
    
    Exposed for use by other modules (entity_resolver, inference_engine).
    """
    extractor = SPOExtractor.__new__(SPOExtractor)
    return extractor._normalize_predicate(predicate, max_words)
