"""
Triple Context Restorer (TCR-QF Pattern)

Implements the Triple Context Restoration and Query-driven Feedback framework
from "How to Mitigate Information Loss in Knowledge Graphs for GraphRAG".

Key Concepts:
1. Triple Context Restoration: Trace each triple back to its source sentence
2. Query-driven Feedback: Identify missing knowledge gaps during reasoning
3. Iterative Enrichment: Use feedback to augment KG with additional triples

Reference: https://arxiv.org/abs/2503.08266
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from difflib import SequenceMatcher

from .schemas import SPOTriple, TextChunk


# =============================================================================
# Contextual Triple with Enhanced Source Grounding
# =============================================================================

@dataclass
class ContextualTriple:
    """
    Enhanced triple with full source context (TCR-QF pattern).
    
    Unlike basic SPOTriple which may have truncated source_text,
    this captures the complete source sentence and precise character offsets.
    """
    subject: str
    predicate: str
    object: str
    confidence: float
    source_sentence: str  # Complete source sentence containing the triple
    char_start: int       # Character offset where evidence begins
    char_end: int         # Character offset where evidence ends
    context_window: str   # Surrounding context (±1 sentence)
    restoration_score: float  # How well the triple matches its source


@dataclass
class MissingKnowledge:
    """Represents a knowledge gap identified by query-driven feedback."""
    question: str          # Sub-question to fill the gap
    reason: str            # Why this knowledge is missing
    related_triples: list  # Existing triples related to this gap
    priority: str          # "high", "medium", "low"


# =============================================================================
# Context Restorer Class
# =============================================================================

class TripleContextRestorer:
    """
    Restores original text context for each extracted triple (TCR-QF).
    
    This addresses the "information loss" problem where converting text to
    triples loses semantic nuances, coreferences, and implicit relationships.
    
    Key Methods:
    - restore_context(): Find/attach original source sentence to each triple
    - identify_missing_knowledge(): Query-driven feedback for knowledge gaps
    - enrich_from_feedback(): Generate new triples from identified gaps
    
    Usage:
        restorer = TripleContextRestorer(gemini_client)
        contextual = await restorer.restore_context(triple, source_texts)
        gaps = await restorer.identify_missing_knowledge(query, triples)
    """
    
    def __init__(
        self,
        gemini_client=None,
        similarity_threshold: float = 0.6,
        context_window_size: int = 1,
    ):
        """
        Initialize the context restorer.
        
        Args:
            gemini_client: GeminiClient for LLM-assisted matching
            similarity_threshold: Minimum similarity for source matching
            context_window_size: Number of surrounding sentences to include
        """
        self.client = gemini_client
        self.similarity_threshold = similarity_threshold
        self.context_window_size = context_window_size
    
    async def restore_context(
        self,
        triple: SPOTriple,
        source_texts: list[str],
    ) -> ContextualTriple:
        """
        Find the source sentence that supports this triple.
        
        Implements TCR-QF triple context restoration by tracing each
        (subject, predicate, object) back to its originating text span.
        
        Args:
            triple: The triple to restore context for
            source_texts: List of source text documents
            
        Returns:
            ContextualTriple with source sentence and character offsets
        """
        # Combine all source texts
        full_text = "\n\n".join(source_texts)
        sentences = self._split_sentences(full_text)
        
        # Build search template from triple
        template = f"{triple.subject} {triple.predicate.replace('_', ' ').lower()} {triple.object}"
        
        # Find best matching sentence
        best_sentence = ""
        best_score = 0.0
        best_idx = -1
        
        for idx, sentence in enumerate(sentences):
            score = self._compute_match_score(template, sentence, triple)
            if score > best_score:
                best_score = score
                best_sentence = sentence
                best_idx = idx
        
        # Get context window (surrounding sentences)
        context_sentences = []
        start_idx = max(0, best_idx - self.context_window_size)
        end_idx = min(len(sentences), best_idx + self.context_window_size + 1)
        for i in range(start_idx, end_idx):
            if i != best_idx:
                context_sentences.append(sentences[i])
        context_window = " ".join(context_sentences)
        
        # Find character offsets in full text
        char_start = full_text.find(best_sentence) if best_sentence else 0
        char_end = char_start + len(best_sentence) if best_sentence else 0
        
        return ContextualTriple(
            subject=triple.subject,
            predicate=triple.predicate,
            object=triple.object,
            confidence=triple.confidence,
            source_sentence=best_sentence or "No matching source found",
            char_start=char_start,
            char_end=char_end,
            context_window=context_window,
            restoration_score=best_score,
        )
    
    async def restore_batch(
        self,
        triples: list[SPOTriple],
        source_texts: list[str],
        max_concurrent: int = 10,
    ) -> list[ContextualTriple]:
        """
        Restore context for multiple triples in parallel.
        
        Args:
            triples: List of triples to process
            source_texts: Source documents
            max_concurrent: Maximum concurrent operations
            
        Returns:
            List of ContextualTriples with restored context
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def restore_with_limit(triple: SPOTriple) -> ContextualTriple:
            async with semaphore:
                return await self.restore_context(triple, source_texts)
        
        tasks = [restore_with_limit(t) for t in triples]
        return await asyncio.gather(*tasks)
    
    async def identify_missing_knowledge(
        self,
        query: str,
        current_triples: list[SPOTriple],
        max_gaps: int = 5,
    ) -> list[MissingKnowledge]:
        """
        Identify knowledge gaps that prevent answering the query (TCR-QF).
        
        This implements the query-driven feedback mechanism that iteratively
        identifies what information is missing from the current knowledge graph.
        
        Args:
            query: The user's question
            current_triples: Currently available triples
            max_gaps: Maximum number of gaps to identify
            
        Returns:
            List of MissingKnowledge items representing gaps
        """
        if not self.client:
            return []
        
        # Format current knowledge
        triples_text = "\n".join(
            f"- ({t.subject}) --[{t.predicate}]-> ({t.object})"
            for t in current_triples[:30]  # Limit for prompt size
        )
        
        prompt = f"""You are a knowledge gap analyst. Given a query and the current knowledge graph, identify what information is MISSING that would be needed to fully answer the query.

QUERY: {query}

CURRENT KNOWLEDGE GRAPH:
{triples_text if triples_text else "Empty - no triples available"}

Identify up to {max_gaps} specific pieces of missing information. For each gap, provide:
1. A specific sub-question that would fill this gap
2. Why this information is missing/needed
3. Which existing triples (if any) relate to this gap
4. Priority (high/medium/low) based on importance for answering the query

Return a JSON array:
[{{
    "question": "What is the data retention period for...",
    "reason": "The query asks about data storage but no retention policies are in the KG",
    "related_triples": ["COMPANY STORES user_data"],
    "priority": "high"
}}]

Focus on GDPR-relevant knowledge gaps: data collection, sharing, retention, rights, third parties.
"""
        
        try:
            response = await self.client.extract_json(prompt)
            
            gaps = []
            if isinstance(response, list):
                for item in response[:max_gaps]:
                    gaps.append(MissingKnowledge(
                        question=item.get("question", "Unknown gap"),
                        reason=item.get("reason", ""),
                        related_triples=item.get("related_triples", []),
                        priority=item.get("priority", "medium"),
                    ))
            
            return gaps
            
        except Exception:
            return []
    
    async def enrich_from_feedback(
        self,
        gaps: list[MissingKnowledge],
        source_texts: list[str],
    ) -> list[SPOTriple]:
        """
        Generate new triples to fill identified knowledge gaps.
        
        This completes the TCR-QF feedback loop by extracting additional
        information from source texts targeted at the identified gaps.
        
        Args:
            gaps: Knowledge gaps from identify_missing_knowledge
            source_texts: Source documents to search for information
            
        Returns:
            New triples addressing the knowledge gaps
        """
        if not self.client or not gaps:
            return []
        
        new_triples = []
        full_text = "\n\n".join(source_texts)[:10000]  # Limit for prompt size
        
        for gap in gaps:
            if gap.priority != "high":
                continue  # Focus on high-priority gaps first
            
            prompt = f"""Extract SPO triples from the text below that answer this specific question:

QUESTION: {gap.question}

SOURCE TEXT:
{full_text[:5000]}

Return a JSON array of triples that answer the question:
[{{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.8}}]

Use UPPERCASE_SNAKE_CASE for predicates. Only include triples that directly address the question.
"""
            
            try:
                response = await self.client.extract_json(prompt)
                
                if isinstance(response, list):
                    for item in response[:3]:  # Max 3 per gap
                        if all(k in item for k in ["subject", "predicate", "object"]):
                            new_triples.append(SPOTriple(
                                subject=str(item["subject"]),
                                predicate=str(item["predicate"]).upper().replace(" ", "_"),
                                object=str(item["object"]),
                                confidence=float(item.get("confidence", 0.6)),
                                source_text=gap.question,  # Mark source as the gap question
                                inferred=True,  # Mark as inferred/gap-filling
                            ))
            except Exception:
                continue
        
        return new_triples
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting (handles common cases)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _compute_match_score(
        self,
        template: str,
        sentence: str,
        triple: SPOTriple,
    ) -> float:
        """
        Compute match score between triple and potential source sentence.
        
        Uses multiple signals:
        - Subject/object presence in sentence
        - Predicate-related terms
        - Sequence similarity
        """
        sentence_lower = sentence.lower()
        template_lower = template.lower()
        
        score = 0.0
        
        # Check for subject presence
        if triple.subject.lower() in sentence_lower:
            score += 0.4
        
        # Check for object presence
        if triple.object.lower() in sentence_lower:
            score += 0.4
        
        # Check for predicate-related terms
        predicate_words = triple.predicate.lower().replace("_", " ").split()
        for word in predicate_words:
            if len(word) > 3 and word in sentence_lower:
                score += 0.1
                break
        
        # Sequence similarity as tiebreaker
        similarity = SequenceMatcher(None, template_lower, sentence_lower).ratio()
        score += similarity * 0.2
        
        return min(score, 1.0)


# =============================================================================
# Convenience Functions
# =============================================================================

async def restore_triple_context(
    triple: SPOTriple,
    source_texts: list[str],
    gemini_client=None,
) -> ContextualTriple:
    """
    Quick context restoration for a single triple.
    
    Args:
        triple: Triple to restore context for
        source_texts: Source documents
        gemini_client: Optional Gemini client for LLM assistance
        
    Returns:
        ContextualTriple with source grounding
    """
    restorer = TripleContextRestorer(gemini_client)
    return await restorer.restore_context(triple, source_texts)


async def find_knowledge_gaps(
    query: str,
    triples: list[SPOTriple],
    gemini_client,
) -> list[MissingKnowledge]:
    """
    Identify knowledge gaps for a query (TCR-QF feedback).
    
    Args:
        query: User's question
        triples: Current knowledge graph triples
        gemini_client: Gemini client for analysis
        
    Returns:
        List of identified knowledge gaps
    """
    restorer = TripleContextRestorer(gemini_client)
    return await restorer.identify_missing_knowledge(query, triples)
