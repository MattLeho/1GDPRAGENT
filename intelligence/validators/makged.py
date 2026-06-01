"""
MAKGED Multi-Agent Validator

Translates 07_integrity_council.json N8N workflow to Python.
Uses 4 parallel agents to validate knowledge graph triples through debate.
"""

import json
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from llm.gemini import GeminiClient
from db.neo4j import get_neo4j_client
from config import get_settings


settings = get_settings()


class Verdict(str, Enum):
    """Agent verdict options."""
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    UNKNOWN = "UNKNOWN"


class Decision(str, Enum):
    """Final decision options."""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class Triple:
    """Knowledge graph triple (subject-predicate-object)."""
    head: str  # Subject
    relation: str  # Predicate
    tail: str  # Object
    
    @classmethod
    def from_dict(cls, data: dict) -> "Triple":
        """Create from dict with flexible key names."""
        return cls(
            head=data.get("subject") or data.get("head") or "Unknown",
            relation=data.get("predicate") or data.get("relation") or "UNKNOWN",
            tail=data.get("object") or data.get("tail") or "Unknown",
        )


@dataclass
class AgentResponse:
    """Response from a validation agent."""
    agent_name: str
    verdict: Verdict
    confidence: float  # 0-10
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ValidationResult:
    """Result of triple validation."""
    success: bool
    triple: Triple
    decision: Decision
    votes: dict  # {"correct": n, "incorrect": m}
    rounds: int
    cypher_statement: Optional[str] = None
    agent_responses: dict = field(default_factory=dict)


# Agent prompts (from N8N workflow)
HEAD_FORWARD_PROMPT = """## HEAD FORWARD AGENT - Round {round}

**Triple:** ({head}) --[{relation}]--> ({tail})
**Source:** {source_text}

You analyze OUTGOING relations FROM the head entity.

1. Consider: What other relations might {head} have as a source?
2. Analyze if the proposed relation fits the pattern for this entity type.
3. {previous_context}

Based on your analysis, determine if this triple is CORRECT or INCORRECT.

Respond with JSON only:
{{
  "verdict": "CORRECT" or "INCORRECT",
  "confidence": 0-10,
  "evidence": ["list of supporting points"],
  "reasoning": "Your analysis"
}}
"""

HEAD_BACKWARD_PROMPT = """## HEAD BACKWARD AGENT - Round {round}

**Triple:** ({head}) --[{relation}]--> ({tail})
**Source:** {source_text}

You analyze INCOMING relations TO the head entity.

1. Consider: What typically points TO {head}?
2. Does the head entity's context support this new outgoing relation?
3. {previous_context}

Based on your analysis, determine if this triple is CORRECT or INCORRECT.

Respond with JSON only:
{{
  "verdict": "CORRECT" or "INCORRECT",
  "confidence": 0-10,
  "evidence": ["list of supporting points"],
  "reasoning": "Your analysis"
}}
"""

TAIL_FORWARD_PROMPT = """## TAIL FORWARD AGENT - Round {round}

**Triple:** ({head}) --[{relation}]--> ({tail})
**Source:** {source_text}

You analyze OUTGOING relations FROM the tail entity.

1. Consider: What does {tail} typically point to?
2. Is this the right type of entity to receive this relation?
3. {previous_context}

Based on your analysis, determine if this triple is CORRECT or INCORRECT.

Respond with JSON only:
{{
  "verdict": "CORRECT" or "INCORRECT",
  "confidence": 0-10,
  "evidence": ["list of supporting points"],
  "reasoning": "Your analysis"
}}
"""

TAIL_BACKWARD_PROMPT = """## TAIL BACKWARD AGENT - Round {round}

**Triple:** ({head}) --[{relation}]--> ({tail})
**Source:** {source_text}

You analyze INCOMING relations TO the tail entity.

1. Consider: What else typically points TO {tail}?
2. Do other entities use similar relations to point here?
3. {previous_context}

Based on your analysis, determine if this triple is CORRECT or INCORRECT.

Respond with JSON only:
{{
  "verdict": "CORRECT" or "INCORRECT",
  "confidence": 0-10,
  "evidence": ["list of supporting points"],
  "reasoning": "Your analysis"
}}
"""


class MAKGEDValidator:
    """
    Multi-Agent Knowledge Graph Error Detection Validator.
    
    Translates 07_integrity_council.json N8N workflow to Python.
    
    Architecture:
    - 4 agents analyze the triple from different perspectives
    - Head Forward: Outgoing from head
    - Head Backward: Incoming to head
    - Tail Forward: Outgoing from tail
    - Tail Backward: Incoming to tail
    
    Voting:
    - 4/4 consensus → immediate decision
    - 3/4 majority → decision
    - 2/2 tie → NEEDS_REVIEW or iterate
    - No majority → iterate (up to max_rounds)
    """
    
    def __init__(self, max_rounds: int = 3):
        """
        Initialize the validator.
        
        Args:
            max_rounds: Maximum discussion rounds (default 3 from N8N)
        """
        self.max_rounds = max_rounds
        self.llm = GeminiClient.get_flash_client()
        self.neo4j = get_neo4j_client()
    
    async def validate(
        self,
        triple: Triple,
        source_text: str = "",
    ) -> ValidationResult:
        """
        Validate a triple using multi-agent debate.
        
        Args:
            triple: The triple to validate
            source_text: Source context for validation
            
        Returns:
            ValidationResult with decision and votes
        """
        agent_responses = {}
        current_round = 1
        
        while current_round <= self.max_rounds:
            # Run all 4 agents in parallel
            responses = await self._run_agents(
                triple=triple,
                source_text=source_text,
                round_num=current_round,
                previous_responses=agent_responses,
            )
            
            # Update agent responses
            for resp in responses:
                agent_responses[resp.agent_name] = {
                    "verdict": resp.verdict.value,
                    "confidence": resp.confidence,
                    "evidence": resp.evidence,
                    "reasoning": resp.reasoning,
                }
            
            # Count votes
            votes = self._count_votes(responses)
            
            # Check for consensus or majority
            if votes["correct"] == 4 or votes["incorrect"] == 4:
                # Full consensus
                decision = Decision.ACCEPT if votes["correct"] == 4 else Decision.REJECT
                break
            elif votes["correct"] >= 3 or votes["incorrect"] >= 3:
                # Majority
                decision = Decision.ACCEPT if votes["correct"] >= 3 else Decision.REJECT
                break
            elif current_round >= self.max_rounds:
                # Max rounds reached, decide based on tie
                if votes["correct"] == votes["incorrect"]:
                    decision = Decision.NEEDS_REVIEW
                else:
                    decision = Decision.ACCEPT if votes["correct"] > votes["incorrect"] else Decision.REJECT
                break
            
            current_round += 1
        
        # Generate Cypher if accepted
        cypher = None
        if decision == Decision.ACCEPT:
            rel = triple.relation.upper().replace(" ", "_")
            # Sanitize for Cypher
            import re
            rel = re.sub(r'[^A-Z_]', '_', rel)
            cypher = (
                f"MERGE (h {{value: '{triple.head.replace(chr(39), chr(39)+chr(39))}'}}) "
                f"MERGE (t {{value: '{triple.tail.replace(chr(39), chr(39)+chr(39))}'}}) "
                f"MERGE (h)-[:{rel}]->(t)"
            )
        
        return ValidationResult(
            success=True,
            triple=triple,
            decision=decision,
            votes=votes,
            rounds=current_round,
            cypher_statement=cypher,
            agent_responses=agent_responses,
        )
    
    async def _run_agents(
        self,
        triple: Triple,
        source_text: str,
        round_num: int,
        previous_responses: dict,
    ) -> list[AgentResponse]:
        """Run all 4 agents in parallel."""
        
        previous_context = ""
        if previous_responses:
            previous_context = f"Previous round arguments: {json.dumps(previous_responses)}"
        else:
            previous_context = "This is the first round of analysis."
        
        # Create agent tasks
        agents = [
            ("head_forward", HEAD_FORWARD_PROMPT),
            ("head_backward", HEAD_BACKWARD_PROMPT),
            ("tail_forward", TAIL_FORWARD_PROMPT),
            ("tail_backward", TAIL_BACKWARD_PROMPT),
        ]
        
        tasks = []
        for agent_name, prompt_template in agents:
            prompt = prompt_template.format(
                round=round_num,
                head=triple.head,
                relation=triple.relation,
                tail=triple.tail,
                source_text=source_text or "No source provided",
                previous_context=previous_context,
            )
            tasks.append(self._run_single_agent(agent_name, prompt))
        
        # Run all agents in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        responses = []
        for i, result in enumerate(results):
            agent_name = agents[i][0]
            if isinstance(result, Exception):
                # Default to UNKNOWN on error
                responses.append(AgentResponse(
                    agent_name=agent_name,
                    verdict=Verdict.UNKNOWN,
                    confidence=5,
                    reasoning=f"Error: {str(result)}",
                ))
            else:
                responses.append(result)
        
        return responses
    
    async def _run_single_agent(
        self,
        agent_name: str,
        prompt: str,
    ) -> AgentResponse:
        """Run a single validation agent."""
        try:
            response = await self.llm.complete(prompt, temperature=0.3)
            return self._parse_agent_response(agent_name, response)
        except Exception as e:
            return AgentResponse(
                agent_name=agent_name,
                verdict=Verdict.UNKNOWN,
                confidence=5,
                reasoning=f"Error: {str(e)}",
            )
    
    def _parse_agent_response(
        self,
        agent_name: str,
        response: str,
    ) -> AgentResponse:
        """Parse agent response from LLM output."""
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found")
            
            verdict_str = data.get("verdict", "UNKNOWN").upper()
            verdict = Verdict.CORRECT if verdict_str == "CORRECT" else (
                Verdict.INCORRECT if verdict_str == "INCORRECT" else Verdict.UNKNOWN
            )
            
            return AgentResponse(
                agent_name=agent_name,
                verdict=verdict,
                confidence=float(data.get("confidence", 5)),
                evidence=data.get("evidence", []),
                reasoning=data.get("reasoning", ""),
            )
            
        except (json.JSONDecodeError, ValueError):
            return AgentResponse(
                agent_name=agent_name,
                verdict=Verdict.UNKNOWN,
                confidence=5,
                reasoning="Failed to parse response",
            )
    
    def _count_votes(self, responses: list[AgentResponse]) -> dict:
        """Count CORRECT vs INCORRECT votes."""
        correct = 0
        incorrect = 0
        
        for resp in responses:
            if resp.verdict == Verdict.CORRECT:
                correct += 1
            elif resp.verdict == Verdict.INCORRECT:
                incorrect += 1
        
        return {"correct": correct, "incorrect": incorrect}


# Convenience function
async def validate_triple(
    triple: dict,
    source_text: str = "",
    max_rounds: int = 3,
) -> ValidationResult:
    """
    Validate a triple using MAKGED.
    
    Convenience wrapper for MAKGEDValidator.
    
    Args:
        triple: Dict with subject/predicate/object or head/relation/tail
        source_text: Source context
        max_rounds: Max discussion rounds
        
    Returns:
        ValidationResult
    """
    validator = MAKGEDValidator(max_rounds=max_rounds)
    return await validator.validate(
        triple=Triple.from_dict(triple),
        source_text=source_text,
    )
