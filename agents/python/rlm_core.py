"""
RLM Core - Recursive Language Model Utilities

This module implements the core RLM (Recursive Language Model) patterns
based on MIT CSAIL research (Zhang, Kraska, Khattab 2512.24601v1).

The key insight: treat long prompts as external environment variables,
enabling programmatic decomposition and recursive LLM calls on snippets.
"""

import re
import json
from typing import Optional, Generator
from dataclasses import dataclass

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Chunk:
    """Represents a chunk of text with metadata."""
    content: str
    start_line: int
    end_line: int
    section: Optional[str] = None

@dataclass
class SearchResult:
    """Result from searching the context."""
    chunk: Chunk
    relevance_score: float
    matched_terms: list[str]


# =============================================================================
# Context Manager
# =============================================================================

class ContextManager:
    """
    Manages a large text document as an external environment variable.
    Provides search, chunking, and section extraction capabilities.
    """
    
    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')
        self.sections = self._extract_sections()
    
    def _extract_sections(self) -> dict[str, tuple[int, int]]:
        """Extract section headers and their line ranges."""
        sections = {}
        current_section = "preamble"
        section_start = 0
        
        # Pattern for article/section headers
        article_pattern = re.compile(r'^(?:Article|Section|Chapter)\s+(\d+)', re.IGNORECASE)
        
        for i, line in enumerate(self.lines):
            match = article_pattern.match(line.strip())
            if match:
                # Save previous section
                sections[current_section] = (section_start, i - 1)
                current_section = f"article_{match.group(1)}"
                section_start = i
        
        # Save last section
        sections[current_section] = (section_start, len(self.lines) - 1)
        return sections
    
    def get_section(self, section_name: str) -> Optional[str]:
        """Get content of a specific section."""
        if section_name not in self.sections:
            return None
        start, end = self.sections[section_name]
        return '\n'.join(self.lines[start:end + 1])
    
    def search(self, query: str, context_lines: int = 5) -> list[SearchResult]:
        """
        Search for query terms in the context.
        Returns matching chunks with surrounding context.
        """
        results = []
        query_terms = query.lower().split()
        
        for i, line in enumerate(self.lines):
            line_lower = line.lower()
            matched = [term for term in query_terms if term in line_lower]
            
            if matched:
                start = max(0, i - context_lines)
                end = min(len(self.lines), i + context_lines + 1)
                
                # Determine which section this belongs to
                section = None
                for sec_name, (sec_start, sec_end) in self.sections.items():
                    if sec_start <= i <= sec_end:
                        section = sec_name
                        break
                
                chunk = Chunk(
                    content='\n'.join(self.lines[start:end]),
                    start_line=start,
                    end_line=end,
                    section=section
                )
                
                results.append(SearchResult(
                    chunk=chunk,
                    relevance_score=len(matched) / len(query_terms),
                    matched_terms=matched
                ))
        
        # Sort by relevance and deduplicate overlapping chunks
        results.sort(key=lambda x: -x.relevance_score)
        return self._deduplicate_results(results)
    
    def _deduplicate_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove overlapping search results, keeping higher relevance."""
        seen_ranges = set()
        deduped = []
        
        for result in results:
            key = (result.chunk.start_line // 10, result.chunk.end_line // 10)
            if key not in seen_ranges:
                seen_ranges.add(key)
                deduped.append(result)
        
        return deduped[:10]  # Return top 10
    
    def chunk_by_size(self, max_chars: int = 4000) -> Generator[Chunk, None, None]:
        """Split context into chunks of roughly max_chars size."""
        current_chunk = []
        current_size = 0
        start_line = 0
        
        for i, line in enumerate(self.lines):
            if current_size + len(line) > max_chars and current_chunk:
                yield Chunk(
                    content='\n'.join(current_chunk),
                    start_line=start_line,
                    end_line=i - 1
                )
                current_chunk = []
                current_size = 0
                start_line = i
            
            current_chunk.append(line)
            current_size += len(line) + 1
        
        if current_chunk:
            yield Chunk(
                content='\n'.join(current_chunk),
                start_line=start_line,
                end_line=len(self.lines) - 1
            )
    
    def search_articles(self, article_numbers: list[int]) -> dict[int, str]:
        """Get content for specific article numbers."""
        results = {}
        for num in article_numbers:
            section_name = f"article_{num}"
            content = self.get_section(section_name)
            if content:
                results[num] = content
        return results


# =============================================================================
# Result Aggregator
# =============================================================================

class ResultAggregator:
    """Aggregates results from multiple sub-LLM calls."""
    
    def __init__(self):
        self.results: list[dict] = []
    
    def add(self, result: dict):
        """Add a sub-result."""
        self.results.append(result)
    
    def synthesize(self) -> dict:
        """Combine all results into a coherent response."""
        if not self.results:
            return {"error": "No results to aggregate"}
        
        # Merge all unique findings
        all_articles = set()
        all_findings = []
        all_recommendations = []
        
        for r in self.results:
            if "articles" in r:
                all_articles.update(r["articles"])
            if "findings" in r:
                all_findings.extend(r["findings"])
            if "recommendations" in r:
                all_recommendations.extend(r["recommendations"])
        
        return {
            "articles": sorted(list(all_articles)),
            "findings": list(dict.fromkeys(all_findings)),  # Dedupe
            "recommendations": list(dict.fromkeys(all_recommendations)),
            "num_sources": len(self.results)
        }
    
    def to_json(self) -> str:
        """Export synthesized results as JSON."""
        return json.dumps(self.synthesize(), indent=2)


# =============================================================================
# Prompt Templates
# =============================================================================

GDPR_ARTICLE_SEARCH_PROMPT = """
Given this user query about GDPR rights:
"{query}"

Search the following GDPR text snippet and identify:
1. Relevant article numbers (e.g., Article 15, Article 17)
2. Key provisions that apply
3. Any exceptions or conditions

GDPR Snippet:
{snippet}

Respond in JSON format:
{{"articles": [15, 17], "provisions": ["...", "..."], "exceptions": ["..."]}}
"""

POLICY_ANALYSIS_PROMPT = """
Analyze this privacy policy section against GDPR requirements:

Policy Section:
{policy_section}

GDPR Context (Article {article}):
{gdpr_context}

Identify:
1. Compliance level (compliant/partial/non-compliant)
2. Specific issues found
3. Required changes

JSON response:
"""

REQUEST_DRAFT_PROMPT = """
Draft a GDPR {request_type} request based on:

User Query: {query}
Company: {company}
Relevant Articles: {articles}
Policy Analysis: {analysis}

The request should:
1. Be formal and professional
2. Cite specific GDPR articles
3. Set a clear deadline (30 days per Article 12)
4. Include identity verification offer

Format as a complete letter.
"""
