"""
Text Chunking for Knowledge Graph Extraction

Implements document chunking with overlap following AI-KG patterns.
Provides both word-based and token-aware chunking for optimal LLM context usage.

Key Features:
- Overlapping chunks to preserve context across boundaries
- Character offset tracking for source grounding (LangExtract requirement)
- Sentence boundary preservation option
- Token-aware sizing for LLM context limits

Source patterns: https://github.com/robert-mcdermott/ai-knowledge-graph
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path

from .schemas import TextChunk, ChunkingConfig


# =============================================================================
# Constants
# =============================================================================

# Sentence-ending patterns for boundary preservation
SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

# Word tokenization pattern (handles contractions, hyphenated words)
WORD_PATTERN = re.compile(r'\S+')

# Default token estimation: ~4 characters per token for English
CHARS_PER_TOKEN_ESTIMATE = 4


# =============================================================================
# Core Chunking Functions (AI-KG Pattern)
# =============================================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """
    Split text into overlapping chunks by word count.
    
    Direct port of AI-KG text_utils.chunk_text() with identical behavior.
    
    Args:
        text: Input text to chunk
        chunk_size: Maximum words per chunk
        overlap: Words to overlap between chunks
        
    Returns:
        List of text chunks as strings
        
    Example:
        >>> chunks = chunk_text("word " * 1000, chunk_size=100, overlap=10)
        >>> len(chunks)  # ~11 chunks with overlap
    """
    # Split text into words
    words = text.split()
    
    # If text is smaller than chunk size, return as single chunk
    if len(words) <= chunk_size:
        return [text] if text.strip() else []
    
    # Create chunks with overlap
    chunks = []
    start = 0
    
    while start < len(words):
        # Calculate end position for this chunk
        end = min(start + chunk_size, len(words))
        
        # Join words for this chunk
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        
        # Move start position for next chunk, accounting for overlap
        start = end - overlap
        
        # If near the end and last chunk would be too small, handle final chunk
        if start < len(words) and start + chunk_size - overlap >= len(words):
            final_chunk = ' '.join(words[start:])
            if final_chunk.strip():
                chunks.append(final_chunk)
            break
    
    return chunks


def chunk_text_with_offsets(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks with character offset tracking.
    
    Enhanced version that tracks character positions for source grounding,
    required for LangExtract-style extraction with precise source mapping.
    
    Args:
        text: Input text to chunk
        chunk_size: Maximum words per chunk
        overlap: Words to overlap between chunks
        
    Returns:
        List of TextChunk objects with offset information
    """
    # Find all word boundaries with positions
    word_spans = [(m.start(), m.end(), m.group()) for m in WORD_PATTERN.finditer(text)]
    
    if not word_spans:
        return []
    
    # If text is smaller than chunk size, return as single chunk
    if len(word_spans) <= chunk_size:
        return [TextChunk(
            text=text.strip(),
            start_offset=0,
            end_offset=len(text),
            chunk_index=0,
            word_count=len(word_spans),
        )]
    
    chunks = []
    chunk_index = 0
    start_word_idx = 0
    
    while start_word_idx < len(word_spans):
        # Calculate end word index for this chunk
        end_word_idx = min(start_word_idx + chunk_size, len(word_spans))
        
        # Get character offsets
        start_char = word_spans[start_word_idx][0]
        end_char = word_spans[end_word_idx - 1][1]
        
        # Extract chunk text using character offsets
        chunk_text = text[start_char:end_char]
        
        chunks.append(TextChunk(
            text=chunk_text,
            start_offset=start_char,
            end_offset=end_char,
            chunk_index=chunk_index,
            word_count=end_word_idx - start_word_idx,
        ))
        
        chunk_index += 1
        
        # Move start position, accounting for overlap
        start_word_idx = end_word_idx - overlap
        
        # Handle final chunk
        if start_word_idx < len(word_spans) and start_word_idx + chunk_size >= len(word_spans):
            final_start_char = word_spans[start_word_idx][0]
            final_end_char = word_spans[-1][1]
            final_text = text[final_start_char:final_end_char]
            
            if final_text.strip():
                chunks.append(TextChunk(
                    text=final_text,
                    start_offset=final_start_char,
                    end_offset=final_end_char,
                    chunk_index=chunk_index,
                    word_count=len(word_spans) - start_word_idx,
                ))
            break
    
    return chunks


def chunk_document(
    document: str | Path,
    config: Optional[ChunkingConfig] = None,
    preserve_sentences: bool = True,
) -> list[TextChunk]:
    """
    Chunk a document with sentence boundary preservation.
    
    Args:
        document: Text content or path to text file
        config: Chunking configuration
        preserve_sentences: If True, avoid splitting mid-sentence
        
    Returns:
        List of TextChunk objects
    """
    config = config or ChunkingConfig()
    
    # Load text if path provided
    if isinstance(document, Path):
        text = document.read_text(encoding='utf-8')
    else:
        text = document
    
    if not preserve_sentences:
        return chunk_text_with_offsets(
            text,
            chunk_size=config.chunk_size,
            overlap=config.overlap,
        )
    
    # Sentence-aware chunking
    return _chunk_with_sentence_boundaries(text, config)


def _chunk_with_sentence_boundaries(
    text: str,
    config: ChunkingConfig,
) -> list[TextChunk]:
    """
    Chunk text while respecting sentence boundaries where possible.
    
    Strategy:
    1. Split into sentences
    2. Accumulate sentences until chunk_size reached
    3. Apply overlap by including trailing sentences from previous chunk
    """
    # Split into sentences
    sentences = SENTENCE_ENDINGS.split(text)
    
    # If only one sentence or few sentences, fall back to word chunking
    if len(sentences) <= 2:
        return chunk_text_with_offsets(
            text,
            chunk_size=config.chunk_size,
            overlap=config.overlap,
        )
    
    chunks = []
    chunk_index = 0
    current_offset = 0
    
    # Track sentences for overlap
    sentence_positions = []
    pos = 0
    for sent in sentences:
        sent_start = text.find(sent, pos)
        if sent_start == -1:
            sent_start = pos
        sent_end = sent_start + len(sent)
        sentence_positions.append((sent_start, sent_end, sent))
        pos = sent_end
    
    i = 0
    while i < len(sentence_positions):
        # Accumulate sentences until chunk_size words reached
        chunk_sentences = []
        chunk_start = sentence_positions[i][0]
        word_count = 0
        
        while i < len(sentence_positions) and word_count < config.chunk_size:
            sent_start, sent_end, sent_text = sentence_positions[i]
            sent_words = len(sent_text.split())
            
            # If adding this sentence exceeds max, check if chunk is non-empty
            if word_count + sent_words > config.max_chunk_size and chunk_sentences:
                break
            
            chunk_sentences.append((sent_start, sent_end, sent_text))
            word_count += sent_words
            i += 1
        
        if not chunk_sentences:
            break
        
        # Build chunk from accumulated sentences
        chunk_end = chunk_sentences[-1][1]
        chunk_text_content = text[chunk_start:chunk_end]
        
        chunks.append(TextChunk(
            text=chunk_text_content,
            start_offset=chunk_start,
            end_offset=chunk_end,
            chunk_index=chunk_index,
            word_count=word_count,
        ))
        chunk_index += 1
        
        # Apply overlap by stepping back
        overlap_words = 0
        overlap_sentences = 0
        for j in range(len(chunk_sentences) - 1, -1, -1):
            sent_words = len(chunk_sentences[j][2].split())
            if overlap_words + sent_words <= config.overlap:
                overlap_words += sent_words
                overlap_sentences += 1
            else:
                break
        
        # Step back for overlap
        if overlap_sentences > 0 and i > 0:
            i -= overlap_sentences
    
    return chunks


# =============================================================================
# Token-Aware Chunking
# =============================================================================

async def chunk_with_token_limit(
    text: str,
    max_tokens: int = 4000,
    overlap_tokens: int = 200,
    tokenizer: Optional[Callable[[str], int]] = None,
) -> list[TextChunk]:
    """
    Chunk text based on token count for LLM context limits.
    
    Uses provided tokenizer or falls back to character-based estimation.
    
    Args:
        text: Input text
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Token overlap between chunks
        tokenizer: Optional function that returns token count for text
        
    Returns:
        List of TextChunk objects sized for LLM context
    """
    # Default tokenizer: estimate based on characters
    if tokenizer is None:
        tokenizer = lambda t: len(t) // CHARS_PER_TOKEN_ESTIMATE
    
    # Convert token limits to approximate word counts
    # Average English word is ~5 chars, ~1.25 tokens
    words_per_token = 0.8
    chunk_size = int(max_tokens * words_per_token)
    overlap = int(overlap_tokens * words_per_token)
    
    # Use word-based chunking with converted sizes
    chunks = chunk_text_with_offsets(text, chunk_size=chunk_size, overlap=overlap)
    
    # Verify and adjust chunks that exceed token limit
    adjusted_chunks = []
    for chunk in chunks:
        token_count = tokenizer(chunk.text)
        
        if token_count <= max_tokens:
            adjusted_chunks.append(chunk)
        else:
            # Split oversized chunk
            sub_chunks = chunk_text_with_offsets(
                chunk.text,
                chunk_size=chunk_size // 2,
                overlap=overlap // 2,
            )
            # Adjust offsets relative to original document
            for sub_chunk in sub_chunks:
                adjusted_chunks.append(TextChunk(
                    text=sub_chunk.text,
                    start_offset=chunk.start_offset + sub_chunk.start_offset,
                    end_offset=chunk.start_offset + sub_chunk.end_offset,
                    chunk_index=len(adjusted_chunks),
                    word_count=sub_chunk.word_count,
                ))
    
    # Renumber chunk indices
    for i, chunk in enumerate(adjusted_chunks):
        adjusted_chunks[i] = TextChunk(
            text=chunk.text,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            chunk_index=i,
            word_count=chunk.word_count,
        )
    
    return adjusted_chunks


# =============================================================================
# Utility Functions
# =============================================================================

def estimate_chunk_count(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> int:
    """
    Estimate number of chunks without actually chunking.
    
    Useful for progress estimation and resource planning.
    """
    word_count = len(text.split())
    
    if word_count <= chunk_size:
        return 1
    
    effective_chunk_size = chunk_size - overlap
    return max(1, (word_count - overlap) // effective_chunk_size + 1)


def get_chunk_context(
    chunks: list[TextChunk],
    chunk_index: int,
    context_chunks: int = 1,
) -> str:
    """
    Get a chunk with surrounding context from adjacent chunks.
    
    Useful for providing additional context during extraction.
    
    Args:
        chunks: All chunks
        chunk_index: Target chunk index
        context_chunks: Number of chunks to include on each side
        
    Returns:
        Combined text with context
    """
    start_idx = max(0, chunk_index - context_chunks)
    end_idx = min(len(chunks), chunk_index + context_chunks + 1)
    
    context_texts = [chunks[i].text for i in range(start_idx, end_idx)]
    return " ".join(context_texts)
