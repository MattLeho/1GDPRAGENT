"""
Entity Resolution and Standardization

Implements AI-KG Phase 2 entity standardization with hybrid approach:
- Text normalization (lowercase, stopword removal)
- Frequency-based canonical form selection
- Root word relationship detection
- LLM-assisted resolution for ambiguous cases

Key Features:
- Special handling for emails, phones, domains, URLs
- Preserves provenance through triple updates
- Configurable LLM usage for cost control

Source patterns: https://github.com/robert-mcdermott/ai-knowledge-graph
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass

from .schemas import SPOTriple


# =============================================================================
# Constants
# =============================================================================

# Stopwords to remove during normalization (from AI-KG)
ENTITY_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", 
    "for", "with", "by", "as", "is", "are", "was", "were"
})

# Email pattern for special handling
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Phone pattern (E.164 and common formats)
PHONE_PATTERN = re.compile(r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$')

# URL pattern
URL_PATTERN = re.compile(r'^https?://')

# Domain pattern
DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Word extraction for normalization
WORD_PATTERN = re.compile(r'\b\w+\b')


# =============================================================================
# Entity Resolver Class
# =============================================================================

class EntityResolver:
    """
    Resolves and standardizes entities across extracted triples.
    
    Follows AI-KG Phase 2 standardization pattern with enhancements for:
    - Email/phone/domain special handling
    - Configurable LLM-assisted resolution
    - Root word matching for related concepts
    
    Usage:
        resolver = EntityResolver(gemini_client)
        standardized = await resolver.standardize_entities(triples, use_llm=True)
    """
    
    def __init__(
        self,
        gemini_client=None,
    ):
        """
        Initialize entity resolver.
        
        Args:
            gemini_client: Optional GeminiClient for LLM-assisted resolution
        """
        self.client = gemini_client
    
    async def standardize_entities(
        self,
        triples: list[SPOTriple],
        use_llm: bool = False,
    ) -> list[SPOTriple]:
        """
        Standardize entity names across all triples.
        
        Following AI-KG entity_standardization.py pattern.
        
        Args:
            triples: Input triples to standardize
            use_llm: Whether to use LLM for ambiguous cases
            
        Returns:
            Triples with standardized entity names
        """
        if not triples:
            return triples
        
        # Validate triples
        valid_triples = [
            t for t in triples 
            if t.subject and t.predicate and t.object
        ]
        
        if not valid_triples:
            return []
        
        # 1. Extract all unique entities
        all_entities = set()
        for triple in valid_triples:
            all_entities.add(triple.subject.lower())
            all_entities.add(triple.object.lower())
        
        # 2. Group similar entities
        entity_groups = self._group_similar_entities(all_entities)
        
        # 3. For each group, choose canonical form
        entity_mapping = self._select_canonical_forms(entity_groups, valid_triples)
        
        # 4. Second pass: root word relationships
        entity_mapping = self._apply_root_word_matching(entity_mapping, all_entities)
        
        # 5. Optional LLM resolution for remaining ambiguities
        if use_llm and self.client:
            ambiguous_groups = [
                variants for normalized, variants in entity_groups.items()
                if len(variants) > 2  # Only resolve highly ambiguous groups
            ]
            if ambiguous_groups:
                llm_mappings = await self._resolve_with_llm(ambiguous_groups)
                entity_mapping.update(llm_mappings)
        
        # 6. Apply standardization to triples
        return self._apply_standardization(valid_triples, entity_mapping)
    
    def _group_similar_entities(
        self,
        entities: set[str],
    ) -> dict[str, list[str]]:
        """
        Group entities by their normalized form.
        
        Following AI-KG pattern for basic normalization grouping.
        """
        entity_groups = defaultdict(list)
        
        # Process by length (longer entities first)
        sorted_entities = sorted(entities, key=lambda x: (-len(x), x))
        
        for entity in sorted_entities:
            # Special handling for structured data
            if self._is_structured_entity(entity):
                # Keep structured entities separate
                normalized = self._normalize_structured(entity)
            else:
                normalized = self.normalize_entity(entity)
            
            if normalized:
                entity_groups[normalized].append(entity)
        
        return dict(entity_groups)
    
    def normalize_entity(self, entity: str) -> str:
        """
        Normalize an entity name for comparison.
        
        Direct port of AI-KG normalize_text function.
        
        Args:
            entity: Entity name to normalize
            
        Returns:
            Normalized string for grouping
        """
        # Lowercase
        entity = entity.lower()
        
        # Extract words, filtering stopwords
        words = [
            word for word in WORD_PATTERN.findall(entity)
            if word not in ENTITY_STOPWORDS
        ]
        
        return " ".join(words)
    
    def _is_structured_entity(self, entity: str) -> bool:
        """Check if entity is a structured type (email, phone, URL, domain)."""
        return bool(
            EMAIL_PATTERN.match(entity) or
            PHONE_PATTERN.match(entity) or
            URL_PATTERN.match(entity) or
            DOMAIN_PATTERN.match(entity)
        )
    
    def _normalize_structured(self, entity: str) -> str:
        """Normalize structured entities with type-specific rules."""
        if EMAIL_PATTERN.match(entity):
            return self._normalize_email(entity)
        elif PHONE_PATTERN.match(entity):
            return self._normalize_phone(entity)
        elif URL_PATTERN.match(entity):
            return self._normalize_url(entity)
        elif DOMAIN_PATTERN.match(entity):
            return self._normalize_domain(entity)
        return entity.lower()
    
    def _normalize_email(self, email: str) -> str:
        """Normalize email address."""
        email = email.lower().strip()
        # Handle Gmail dots (a.b.c@gmail = abc@gmail)
        if "@gmail" in email:
            local, domain = email.split("@", 1)
            local = local.replace(".", "")
            # Remove +suffix
            if "+" in local:
                local = local.split("+")[0]
            return f"{local}@{domain}"
        return email
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to digits only."""
        digits = re.sub(r'[^\d+]', '', phone)
        return digits
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to domain."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain name."""
        return domain.lower().strip()
    
    def _select_canonical_forms(
        self,
        entity_groups: dict[str, list[str]],
        triples: list[SPOTriple],
    ) -> dict[str, str]:
        """
        Select canonical form for each entity group.
        
        Uses frequency-based selection: most common form, then shortest.
        Following AI-KG pattern.
        """
        mapping = {}
        
        for group_key, variants in entity_groups.items():
            if len(variants) == 1:
                # Only one variant, use it
                mapping[variants[0]] = variants[0]
            else:
                # Count occurrences in triples
                variant_counts = defaultdict(int)
                for triple in triples:
                    subj_lower = triple.subject.lower()
                    obj_lower = triple.object.lower()
                    for variant in variants:
                        if subj_lower == variant:
                            variant_counts[variant] += 1
                        if obj_lower == variant:
                            variant_counts[variant] += 1
                
                # Select most frequent, then shortest
                canonical = sorted(
                    variants,
                    key=lambda x: (-variant_counts[x], len(x))
                )[0]
                
                for variant in variants:
                    mapping[variant] = canonical
        
        return mapping
    
    def _apply_root_word_matching(
        self,
        mapping: dict[str, str],
        all_entities: set[str],
    ) -> dict[str, str]:
        """
        Apply root word matching to catch related concepts.
        
        E.g., "capitalism" and "capitalist decay" share root "capital".
        From AI-KG entity_standardization.py second pass.
        """
        additional = {}
        
        # Get standardized names after first pass
        standardized = set(mapping.values())
        
        for entity in standardized:
            words = entity.split()
            if not words:
                continue
            
            root = words[0] if len(words[0]) >= 4 else entity
            
            # Find other entities sharing this root
            for other in standardized:
                if other == entity:
                    continue
                
                other_words = other.split()
                if not other_words:
                    continue
                
                # Check if root matches
                other_root = other_words[0] if len(other_words[0]) >= 4 else other
                
                if root == other_root and len(root) >= 4:
                    # Use shorter as canonical
                    if len(entity) <= len(other):
                        additional[other] = entity
                    else:
                        additional[entity] = other
        
        # Update mapping with additional standardizations
        result = mapping.copy()
        for entity, canonical in additional.items():
            if entity in result:
                result[entity] = canonical
        
        return result
    
    async def _resolve_with_llm(
        self,
        entity_groups: list[list[str]],
    ) -> dict[str, str]:
        """
        Use LLM to resolve ambiguous entity groups.
        
        Args:
            entity_groups: List of entity variant groups
            
        Returns:
            Mapping from variants to canonical forms
        """
        if not self.client or not entity_groups:
            return {}
        
        # Build prompt
        groups_text = "\n".join(
            f"Group {i+1}: {', '.join(variants)}"
            for i, variants in enumerate(entity_groups)
        )
        
        prompt = f"""You are an entity resolution expert. Given these groups of entity names that might refer to the same thing, select the best canonical name for each group.

ENTITY GROUPS:
{groups_text}

For each group, choose the most appropriate canonical name. Consider:
- Prefer official names over abbreviations
- Prefer full names over nicknames
- Prefer consistent formatting

Return a JSON object with canonical names as keys and arrays of all variants as values.
Example: {{"Google LLC": ["google", "google llc", "google inc."]}}"""
        
        try:
            response = await self.client.extract_json(prompt)
            
            if isinstance(response, dict):
                mapping = {}
                for canonical, variants in response.items():
                    if isinstance(variants, list):
                        for variant in variants:
                            mapping[str(variant).lower()] = canonical
                return mapping
            return {}
            
        except Exception:
            return {}
    
    def _apply_standardization(
        self,
        triples: list[SPOTriple],
        mapping: dict[str, str],
    ) -> list[SPOTriple]:
        """
        Apply entity mapping to all triples.
        
        Creates new SPOTriple objects with standardized names
        while preserving other fields.
        """
        standardized = []
        
        for triple in triples:
            subj_lower = triple.subject.lower()
            obj_lower = triple.object.lower()
            
            new_subject = mapping.get(subj_lower, triple.subject)
            new_object = mapping.get(obj_lower, triple.object)
            
            # If either entity was standardized, create new triple
            if new_subject != triple.subject or new_object != triple.object:
                standardized.append(SPOTriple(
                    subject=new_subject,
                    predicate=triple.predicate,
                    object=new_object,
                    confidence=triple.confidence,
                    source_chunk=triple.source_chunk,
                    source_text=triple.source_text,
                    inferred=triple.inferred,
                ))
            else:
                standardized.append(triple)
        
        return standardized


# =============================================================================
# Convenience Functions
# =============================================================================

async def standardize_entities(
    triples: list[SPOTriple],
    gemini_client=None,
    use_llm: bool = False,
) -> list[SPOTriple]:
    """
    Quick entity standardization with default settings.
    
    Args:
        triples: Triples to standardize
        gemini_client: Optional GeminiClient for LLM resolution
        use_llm: Whether to use LLM for ambiguous cases
        
    Returns:
        Standardized triples
    """
    resolver = EntityResolver(gemini_client)
    return await resolver.standardize_entities(triples, use_llm=use_llm)


def resolve_entity_variants(entities: set[str]) -> dict[str, str]:
    """
    Resolve entity variants without LLM.
    
    Returns mapping from variant to canonical form.
    """
    resolver = EntityResolver()
    groups = resolver._group_similar_entities(entities)
    return resolver._select_canonical_forms(groups, [])
