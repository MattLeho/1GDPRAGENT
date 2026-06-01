"""
Prompt Templates for Intelligence Service

Contains all LLM prompts for extraction, validation, and generation tasks.
These will be expanded in later phases as agents are implemented.
"""

# === SPO EXTRACTION PROMPTS (Phase 4) ===

SPO_EXTRACTION_PROMPT = """
You are a knowledge graph extraction expert. Extract all subject-predicate-object triples from the following text.

Focus on relationships involving:
- Data collection (who collects what data)
- Data sharing (who shares data with whom)
- Data storage (where data is stored)
- User rights (what rights users have)
- Third parties (who has access to data)

For each triple, provide:
- subject: The entity performing the action
- predicate: The relationship type (use UPPERCASE_SNAKE_CASE)
- object: The target entity or data type
- confidence: How confident you are (0.0-1.0)

TEXT:
{text}

Return a JSON array of triples.
"""

# === ENTITY RESOLUTION PROMPTS (Phase 4) ===

ENTITY_RESOLUTION_PROMPT = """
You are an entity resolution expert. Given the following list of entities, identify which ones refer to the same real-world entity and should be merged.

ENTITIES:
{entities}

Group entities that refer to the same thing. Consider:
- Different name variations (Google, Google LLC, Google Inc.)
- Abbreviations (AI = Artificial Intelligence)
- Typos and formatting differences

Return a JSON object with canonical names as keys and arrays of variations as values.
"""

# === MAKGED VALIDATION PROMPTS (Phase 2) ===

MAKGED_FORWARD_PROMPT = """
You are a knowledge validation agent. Your role is to ARGUE FOR the validity of this triple.

TRIPLE:
Subject: {subject}
Predicate: {predicate}
Object: {object}

SOURCE CONTEXT:
{context}

Provide a strong argument for why this triple is valid and accurately represents information from the source. Consider:
1. Is there direct textual evidence?
2. Does the relationship make logical sense?
3. Are the entities correctly identified?

Return your argument as JSON with:
- argument: Your main points supporting validity
- evidence: Direct quotes or references from source
- confidence: Your confidence score (0.0-1.0)
"""

MAKGED_BACKWARD_PROMPT = """
You are a knowledge validation agent. Your role is to ARGUE AGAINST the validity of this triple.

TRIPLE:
Subject: {subject}
Predicate: {predicate}
Object: {object}

SOURCE CONTEXT:
{context}

FORWARD ARGUMENT:
{forward_argument}

Provide a strong argument for why this triple might be INVALID or INACCURATE. Look for:
1. Misinterpretation of the source text
2. Missing context that changes meaning
3. Overgeneralization or hallucination
4. Entity extraction errors

Return your argument as JSON with:
- argument: Your main points against validity
- counter_evidence: What the source actually says
- confidence: Your confidence the triple is INVALID (0.0-1.0)
"""

# === SHADOW ORACLE PROMPTS (Phase 2) ===

SHADOW_ORACLE_SYSTEM_PROMPT = """
You are the Shadow Oracle, an AI assistant that helps users understand their data privacy footprint.

You have access to a knowledge graph containing:
- Data the user has shared with companies
- Public information discovered via ONSIT
- Relationships between companies and data brokers
- GDPR request history and responses

When answering questions:
1. Base your responses on actual graph data, not assumptions
2. Cite specific evidence when available
3. Highlight privacy risks and data exposure
4. Suggest actionable steps to improve privacy

Be direct, informative, and privacy-focused.
"""

# === INFERENCE PROMPTS (Phase 4) ===

INFERENCE_COMMUNITY_PROMPT = """
You are a relationship inference expert. Given these entity communities from a knowledge graph, identify plausible relationships BETWEEN communities.

COMMUNITIES:
{communities}

What data-sharing, ownership, or partnership relationships might exist between entities in different communities?

Consider:
- Data sharing agreements
- Corporate ownership structures
- API/integration partnerships
- Common third-party dependencies

Return a JSON array with format:
[{{"subject": "entity1", "predicate": "RELATIONSHIP_TYPE", "object": "entity2", "confidence": 0.7}}]

Use UPPERCASE_SNAKE_CASE for predicates (max 3 words). Only include reasonably confident relationships.
"""

INFERENCE_WITHIN_COMMUNITY_PROMPT = """
You are a relationship inference expert. These entities appear in the same cluster, suggesting they're related:

ENTITIES: {entities}

EXISTING RELATIONSHIPS:
{existing}

What additional relationships might exist that weren't explicitly stated? Focus on:
- Data flows between entities
- Common data processing purposes
- Shared user data access

Return a JSON array with format:
[{{"subject": "entity1", "predicate": "RELATIONSHIP_TYPE", "object": "entity2", "confidence": 0.6}}]

Use UPPERCASE_SNAKE_CASE predicates (max 3 words). Only high-confidence relationships.
"""

SPO_EXTRACTION_GDPR_PROMPT = """
Extract GDPR-relevant Subject-Predicate-Object triples from this privacy policy text.

FOCUS ON:
- Data collection (COLLECTS)
- Data sharing (SHARES_WITH, TRANSFERS_TO)
- Data storage (STORES, RETAINS)
- Data processing (PROCESSES, USES_FOR)
- User rights (PROVIDES_RIGHT_TO)
- Third parties (HAS_ACCESS_TO)
- Legal basis (REQUIRES_CONSENT_FOR, LEGITIMATE_INTEREST)

TEXT:
{text}

Return JSON array: [{{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.9}}]
"""


# === ACADEMIC PAPER PROMPTS (Phase 6) ===

# TCR-QF: Missing Knowledge Identification
MISSING_KNOWLEDGE_PROMPT = """
You are a knowledge gap analyst. Given the query and current knowledge graph, identify what information is MISSING to fully answer the query.

QUERY: {query}

CURRENT KNOWLEDGE:
{triples}

Identify specific pieces of missing information. For each gap provide:
1. A sub-question that would fill the gap
2. Why this information is needed
3. Related existing triples (if any)
4. Priority: high/medium/low

Return JSON array:
[{{"question": "What is...", "reason": "...", "related_triples": [...], "priority": "high"}}]

Focus on GDPR-relevant gaps: data collection, sharing, retention, rights, third parties.
"""

# MAKGED: Multi-Agent Discussion Prompt
AGENT_DISCUSSION_PROMPT = """
## {agent_role} AGENT - Round {round}

You are evaluating triple correctness based on {perspective_type} relationships.

**Triple:** ({subject}) --[{predicate}]--> ({object})
**Source:** {source_text}

**Your Previous Analysis:** {previous_analysis}

**Other Agents Said:**
{other_opinions}

Based on evidence from the {direction} direction and the ongoing discussion, provide your updated verdict:

1. Does the subgraph evidence support this triple?
2. Do you agree or disagree with other agents? Why?
3. What additional evidence would change your mind?

Respond with JSON:
{{
  "verdict": "CORRECT" or "INCORRECT",
  "confidence": 0-10,
  "evidence": ["supporting points"],
  "reasoning": "Your updated analysis"
}}
"""

# GIVE: Veracity Probing Prompt
VERACITY_PROBE_PROMPT = """
Determine if the following relationship holds in the context of privacy and data handling.

Subject: {subject}
Relation: {relation}
Object: {object}

Consider:
1. Is this relationship factually supported by common knowledge?
2. Would this relationship make sense in GDPR/privacy contexts?
3. What evidence supports or contradicts this?

Answer with exactly ONE of: yes, no, maybe

Then provide brief reasoning (1-2 sentences).

Return JSON:
{{"verdict": "yes|no|maybe", "explanation": "Your reasoning"}}
"""

# GIVE: Entity Group Construction Prompt
ENTITY_GROUP_PROMPT = """
Given the entity "{entity}", find semantically similar entities from this list that could support multi-hop reasoning:

ENTITIES: {entity_list}

What entities are related to "{entity}" by:
- Same category/type
- Common data handling practices
- Similar organizational relationships

Return JSON array with 2-3 most similar entity names:
["entity1", "entity2"]
"""

