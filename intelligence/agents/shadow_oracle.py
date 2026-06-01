"""
Shadow Oracle Agent

Translates 06_shadow_oracle.json N8N workflow to Python.
Provides RAG-based Q&A interface for the knowledge graph.
"""

import json
from typing import Optional
from dataclasses import dataclass, field

from llm.gemini import GeminiClient
from llm.prompts import SHADOW_ORACLE_SYSTEM_PROMPT
from db.neo4j import get_neo4j_client
from config import get_settings


settings = get_settings()


@dataclass
class QueryResult:
    """Result of a Shadow Oracle query."""
    question: str
    answer: str
    evidence: list[dict] = field(default_factory=list)
    graph_context: list[dict] = field(default_factory=list)
    confidence: float = 0.0


class ShadowOracleAgent:
    """
    Shadow Oracle - Privacy-focused Q&A Agent.
    
    Translates 06_shadow_oracle.json N8N workflow to Python.
    
    Features:
    - Natural language queries about user's data
    - Graph context retrieval
    - Privacy risk highlighting
    - Evidence citation
    """
    
    def __init__(self):
        """Initialize the Shadow Oracle."""
        self.llm = GeminiClient.get_pro_client()  # Pro for quality responses
        self.neo4j = get_neo4j_client()
    
    async def query(
        self,
        question: str,
        user_id: str = "root",
    ) -> QueryResult:
        """
        Answer a question about the user's data.
        
        Args:
            question: Natural language question
            user_id: User identifier (default: root)
            
        Returns:
            QueryResult with answer and evidence
        """
        # Retrieve relevant graph context
        graph_context = await self._get_graph_context(question, user_id)
        
        # Generate answer with context
        answer, evidence, confidence = await self._generate_answer(
            question=question,
            graph_context=graph_context,
        )
        
        return QueryResult(
            question=question,
            answer=answer,
            evidence=evidence,
            graph_context=graph_context,
            confidence=confidence,
        )
    
    async def _get_graph_context(
        self,
        question: str,
        user_id: str,
    ) -> list[dict]:
        """Retrieve relevant graph context for the question."""
        context = []
        
        # Query 1: Get user's companies and data
        try:
            companies_query = """
            MATCH (u:User {uid: $user_id})-[:HAS_ACCOUNT]->(a:Account)-[:HELD_BY]->(c:Company)
            OPTIONAL MATCH (c)-[:COLLECTS]->(d:DataPoint)
            RETURN c.name as company, collect(DISTINCT d.category) as data_categories,
                   count(d) as data_points
            LIMIT 10
            """
            results = await self.neo4j.query(companies_query, {"user_id": user_id})
            for r in results:
                context.append({
                    "type": "company_data",
                    "company": r.get("company"),
                    "categories": r.get("data_categories", []),
                    "data_points": r.get("data_points", 0),
                })
        except Exception:
            pass
        
        # Query 2: Get shared attributes (emails, phones, etc.)
        try:
            attributes_query = """
            MATCH (u:User {uid: $user_id})-[:HAS_ACCOUNT]->(a:Account)-[:LINKED_TO]->(attr:Attribute)
            RETURN attr.type as type, attr.value as value, 
                   collect(DISTINCT a.platform) as platforms
            LIMIT 20
            """
            results = await self.neo4j.query(attributes_query, {"user_id": user_id})
            for r in results:
                context.append({
                    "type": "shared_attribute",
                    "attr_type": r.get("type"),
                    "value": r.get("value"),
                    "shared_with": r.get("platforms", []),
                })
        except Exception:
            pass
        
        # Query 3: Keyword-based search (if question contains specific terms)
        keywords = self._extract_keywords(question)
        if keywords:
            try:
                keyword_query = """
                MATCH (n)
                WHERE any(prop in keys(n) WHERE 
                    toString(n[prop]) CONTAINS $keyword)
                RETURN labels(n) as labels, properties(n) as props
                LIMIT 5
                """
                for keyword in keywords[:3]:  # Limit keywords
                    results = await self.neo4j.query(keyword_query, {"keyword": keyword})
                    for r in results:
                        context.append({
                            "type": "keyword_match",
                            "keyword": keyword,
                            "labels": r.get("labels", []),
                            "properties": r.get("props", {}),
                        })
            except Exception:
                pass
        
        return context
    
    def _extract_keywords(self, question: str) -> list[str]:
        """Extract potential keywords from the question."""
        # Simple keyword extraction - could be enhanced with NLP
        stopwords = {
            "who", "what", "where", "when", "why", "how",
            "is", "are", "was", "were", "has", "have", "had",
            "my", "the", "a", "an", "of", "to", "in", "for",
            "with", "on", "at", "by", "about", "does", "do",
        }
        
        words = question.lower().replace("?", "").split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords
    
    async def _generate_answer(
        self,
        question: str,
        graph_context: list[dict],
    ) -> tuple[str, list[dict], float]:
        """Generate answer using LLM with graph context."""
        
        # Format context for prompt
        context_str = json.dumps(graph_context, indent=2) if graph_context else "No data found."
        
        prompt = f"""{SHADOW_ORACLE_SYSTEM_PROMPT}

## USER QUESTION
{question}

## KNOWLEDGE GRAPH DATA
```json
{context_str}
```

Based on the knowledge graph data above, answer the user's question.
If the data doesn't contain relevant information, say so clearly.
Highlight any privacy risks or concerns.

Respond with JSON:
{{
  "answer": "Your detailed answer",
  "evidence": ["list of specific facts from the data"],
  "confidence": 0.0-1.0,
  "privacy_risks": ["any risks identified"]
}}
"""
        
        try:
            response = await self.llm.complete(prompt, temperature=0.4)
            
            # Parse response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return (
                    data.get("answer", response),
                    [{"fact": e} for e in data.get("evidence", [])],
                    float(data.get("confidence", 0.5)),
                )
            else:
                return response, [], 0.5
                
        except Exception as e:
            return f"I couldn't process your question: {str(e)}", [], 0.0


# Convenience function
async def shadow_query(
    question: str,
    user_id: str = "root",
) -> QueryResult:
    """
    Query the Shadow Oracle.
    
    Convenience wrapper for ShadowOracleAgent.
    """
    agent = ShadowOracleAgent()
    return await agent.query(question, user_id)
