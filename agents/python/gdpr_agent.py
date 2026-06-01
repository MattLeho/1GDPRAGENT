"""
GDPR Request Drafting Agent

This agent uses the Recursive Language Model (RLM) approach to:
1. Load and index the UK GDPR regulation
2. Analyze privacy policies against GDPR requirements
3. Draft compliant data access/deletion requests

Reference: MIT CSAIL RLM paper (Zhang, Kraska, Khattab)
"""

import os
import json
import re
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import httpx
from google import genai

from rlm_core import ContextManager, ResultAggregator, Chunk

# =============================================================================
# Configuration
# =============================================================================

# Path to GDPR Law document
GDPR_LAW_PATH = Path(__file__).parent.parent.parent / "App_Context_and_Plan" / "GDPR Law.md"

# Model configurations
GEMINI_FLASH = "gemini-3-flash-preview"
GEMINI_PRO = "gemini-3-pro-preview"

# Request types
REQUEST_TYPES = {
    "access": "Subject Access Request (Article 15)",
    "erasure": "Erasure Request - Right to be Forgotten (Article 17)",
    "rectification": "Rectification Request (Article 16)",
    "portability": "Data Portability Request (Article 20)",
    "objection": "Objection to Processing (Article 21)",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DraftRequest:
    """A drafted GDPR request."""
    request_type: str
    company: str
    subject: str
    body: str
    articles_cited: list[int]
    deadline_days: int = 30


@dataclass
class PolicyAnalysis:
    """Analysis result for a privacy policy."""
    company: str
    compliance_score: float
    findings: list[str]
    data_categories: list[str]
    contact_info: dict
    recommendations: list[str]


# =============================================================================
# GDPR Request Drafter
# =============================================================================

class GDPRRequestDrafter:
    """
    RLM-based GDPR request drafting agent.
    
    Uses context management to handle the 7000+ line GDPR regulation
    and recursive LLM calls for analysis and drafting.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key (falls back to env var)."""
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set GOOGLE_API_KEY or GEMINI_API_KEY")
        
        self.client = genai.Client(api_key=self.api_key)
        self.gdpr_context: Optional[ContextManager] = None
        self._load_gdpr()
    
    def _load_gdpr(self):
        """Load GDPR law as context manager."""
        if GDPR_LAW_PATH.exists():
            content = GDPR_LAW_PATH.read_text(encoding='utf-8')
            self.gdpr_context = ContextManager(content)
            print(f"[GDPR Agent] Loaded GDPR with {len(self.gdpr_context.lines)} lines, {len(self.gdpr_context.sections)} sections")
        else:
            print(f"[GDPR Agent] Warning: GDPR Law not found at {GDPR_LAW_PATH}")
    
    async def _call_llm(self, prompt: str, model: str = GEMINI_FLASH) -> str:
        """Make an async LLM call."""
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=prompt
            )
            return response.text or ""
        except Exception as e:
            print(f"[GDPR Agent] LLM call failed: {e}")
            return ""
    
    async def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        try:
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
            if json_match:
                return json.loads(json_match.group(1))
            # Otherwise try parsing directly
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse response", "raw": response[:500]}
    
    async def find_relevant_articles(self, query: str) -> list[int]:
        """
        RLM Step 1: Search GDPR context for relevant articles.
        Uses chunking and recursive search.
        """
        if not self.gdpr_context:
            return [15, 17]  # Default fallback
        
        # Search for query terms
        results = self.gdpr_context.search(query, context_lines=10)
        
        # Extract article references
        article_pattern = re.compile(r'Article\s+(\d+)', re.IGNORECASE)
        found_articles = set()
        
        for result in results[:5]:  # Top 5 results
            matches = article_pattern.findall(result.chunk.content)
            found_articles.update(int(m) for m in matches)
        
        # Also check for common keywords
        keyword_articles = {
            "access": [12, 15],
            "delete": [17],
            "erasure": [17],
            "rectify": [16],
            "correct": [16],
            "portability": [20],
            "transfer": [20],
            "object": [21],
            "consent": [6, 7],
            "children": [8],
        }
        
        for keyword, articles in keyword_articles.items():
            if keyword in query.lower():
                found_articles.update(articles)
        
        return sorted(list(found_articles)) or [15, 17]
    
    async def get_article_content(self, article_numbers: list[int]) -> dict[int, str]:
        """
        RLM Step 2: Get specific article content from GDPR.
        """
        if not self.gdpr_context:
            return {}
        
        return self.gdpr_context.search_articles(article_numbers)
    
    async def analyze_policy(self, policy_text: str, company: str) -> PolicyAnalysis:
        """
        Analyze a privacy policy for GDPR compliance.
        Uses recursive chunking for long policies.
        """
        aggregator = ResultAggregator()
        policy_context = ContextManager(policy_text)
        
        # Chunk policy and analyze each chunk
        for i, chunk in enumerate(policy_context.chunk_by_size(3000)):
            prompt = f"""Analyze this privacy policy section for GDPR compliance.

Company: {company}
Section {i + 1}:
{chunk.content}

Return JSON with:
{{
    "data_categories": ["list of personal data types collected"],
    "lawful_bases": ["consent", "contract", etc.],
    "retention_periods": ["if mentioned"],
    "third_party_sharing": ["list of third parties"],
    "issues": ["compliance issues found"],
    "contact_info": {{"dpo_email": "", "address": ""}}
}}
"""
            response = await self._call_llm(prompt)
            result = await self._parse_json_response(response)
            aggregator.add(result)
        
        # Synthesize results
        synthesis = aggregator.synthesize()
        
        # Calculate compliance score
        issues_count = len(synthesis.get("findings", []))
        compliance_score = max(0, 100 - (issues_count * 10))
        
        return PolicyAnalysis(
            company=company,
            compliance_score=compliance_score,
            findings=synthesis.get("findings", []),
            data_categories=synthesis.get("articles", []),  # Mapped from synthesis
            contact_info={},
            recommendations=synthesis.get("recommendations", [])
        )
    
    async def draft_request(
        self,
        request_type: str,
        company: str,
        user_query: str,
        user_name: str,
        user_email: str,
        policy_url: Optional[str] = None
    ) -> DraftRequest:
        """
        Main entry point: Draft a GDPR request.
        
        Uses the full RLM pipeline:
        1. Find relevant GDPR articles
        2. Get article content
        3. Synthesize into a formal request
        """
        # Step 1: Find relevant articles
        articles = await self.find_relevant_articles(user_query)
        
        # Step 2: Get article content
        article_content = await self.get_article_content(articles)
        article_summary = "\n\n".join([
            f"**Article {num}**:\n{content[:500]}..." 
            for num, content in article_content.items()
        ])
        
        # Step 3: Determine request type
        request_title = REQUEST_TYPES.get(request_type, REQUEST_TYPES["access"])
        
        # Step 4: Draft the request using Gemini Pro
        prompt = f"""You are a GDPR compliance expert. Draft a formal {request_title} to {company}.

User Information:
- Name: {user_name}
- Email: {user_email}
- Request: {user_query}

Relevant GDPR Articles (cite these):
{article_summary}

Requirements:
1. Use formal, professional language
2. Cite specific GDPR articles with their numbers
3. Set a 30-day deadline per Article 12(3)
4. Offer to provide identity verification
5. Request confirmation of receipt
6. Mention right to lodge complaint with ICO if ignored

Format the response as a complete, ready-to-send letter.
Do NOT include placeholders - use the provided information.
"""
        
        letter = await self._call_llm(prompt, model=GEMINI_PRO)
        
        # Generate subject line
        subject = f"{request_title} - {user_name}"
        
        return DraftRequest(
            request_type=request_type,
            company=company,
            subject=subject,
            body=letter,
            articles_cited=articles,
            deadline_days=30
        )
    
    async def batch_draft(
        self,
        companies: list[str],
        request_type: str,
        user_query: str,
        user_name: str,
        user_email: str
    ) -> list[DraftRequest]:
        """Draft requests to multiple companies in parallel."""
        tasks = [
            self.draft_request(request_type, company, user_query, user_name, user_email)
            for company in companies
        ]
        return await asyncio.gather(*tasks)


# =============================================================================
# Factory Function
# =============================================================================

def create_agent(api_key: Optional[str] = None) -> GDPRRequestDrafter:
    """Factory function to create a GDPR request drafter."""
    return GDPRRequestDrafter(api_key)


# =============================================================================
# CLI for Testing
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        agent = create_agent()
        
        # Test article search
        articles = await agent.find_relevant_articles("I want to delete my data")
        print(f"Relevant articles: {articles}")
        
        # Test draft
        draft = await agent.draft_request(
            request_type="erasure",
            company="Example Corp",
            user_query="Please delete all my personal data from your systems",
            user_name="John Doe",
            user_email="john@example.com"
        )
        print(f"\n=== Draft Request ===\n")
        print(f"Subject: {draft.subject}")
        print(f"Articles: {draft.articles_cited}")
        print(f"\n{draft.body}")
    
    asyncio.run(test())
