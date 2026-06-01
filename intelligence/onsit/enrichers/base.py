"""
Base Enricher Class

Abstract base class for all ONSIT enrichers following Flowsint pattern.
Source: https://github.com/reconurge/flowsint

Enrichers transform entities into new entities:
- Input: Entity of type X
- Output: List of entities of type(s) Y
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
import asyncio

from ..models import ONSITEntity, EntityType


class BaseEnricher(ABC):
    """
    Abstract base class for entity enrichers.
    
    Enrichers must define:
    - name: Unique enricher identifier
    - input_type: EntityType this enricher accepts
    - output_types: List of EntityTypes this enricher can produce
    - enrich(): Async method to perform enrichment
    
    Usage:
        class EmailGravatarEnricher(BaseEnricher):
            name = "email_gravatar"
            input_type = EntityType.EMAIL
            output_types = [EntityType.GRAVATAR]
            
            async def enrich(self, entity: Email) -> list[Gravatar]:
                # ...implementation
    """
    
    # Subclasses must define these
    name: str = "base"
    input_type: EntityType = None
    output_types: list[EntityType] = []
    
    # Rate limiting configuration
    rate_limit: float = 1.0  # Seconds between requests
    max_retries: int = 3
    timeout: int = 30
    
    # Optional API key requirement
    requires_api_key: bool = False
    api_key_name: str = ""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize enricher with optional API key.
        
        Args:
            api_key: API key for enrichers that require authentication
        """
        self.api_key = api_key
        self._last_request: Optional[datetime] = None
    
    def can_enrich(self, entity: ONSITEntity) -> bool:
        """
        Check if this enricher can process the given entity.
        
        Args:
            entity: Entity to check
            
        Returns:
            True if entity type matches input_type
        """
        return entity.entity_type == self.input_type
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        if self._last_request is not None:
            elapsed = (datetime.utcnow() - self._last_request).total_seconds()
            if elapsed < self.rate_limit:
                await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request = datetime.utcnow()
    
    @abstractmethod
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        """
        Perform enrichment on an entity.
        
        Args:
            entity: Input entity to enrich
            
        Returns:
            List of new entities discovered from enrichment
        """
        pass
    
    async def safe_enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        """
        Safely enrich with rate limiting and error handling.
        
        Args:
            entity: Input entity
            
        Returns:
            List of entities (empty on error)
        """
        if not self.can_enrich(entity):
            return []
        
        await self._rate_limit()
        
        for attempt in range(self.max_retries):
            try:
                results = await asyncio.wait_for(
                    self.enrich(entity),
                    timeout=self.timeout
                )
                # Tag results with source
                for result in results:
                    result.source = f"enricher:{self.name}"
                return results
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    return []
            except Exception:
                if attempt == self.max_retries - 1:
                    return []
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return []
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"


class EnricherRegistry:
    """
    Registry for managing available enrichers.
    
    Usage:
        registry = EnricherRegistry()
        registry.register(EmailGravatarEnricher())
        enrichers = registry.get_for_type(EntityType.EMAIL)
    """
    
    def __init__(self):
        self._enrichers: dict[str, BaseEnricher] = {}
        self._by_input_type: dict[EntityType, list[BaseEnricher]] = {}
    
    def register(self, enricher: BaseEnricher) -> None:
        """Register an enricher."""
        self._enrichers[enricher.name] = enricher
        
        if enricher.input_type not in self._by_input_type:
            self._by_input_type[enricher.input_type] = []
        self._by_input_type[enricher.input_type].append(enricher)
    
    def get(self, name: str) -> Optional[BaseEnricher]:
        """Get enricher by name."""
        return self._enrichers.get(name)
    
    def get_for_type(self, entity_type: EntityType) -> list[BaseEnricher]:
        """Get all enrichers for a given entity type."""
        return self._by_input_type.get(entity_type, [])
    
    def all(self) -> list[BaseEnricher]:
        """Get all registered enrichers."""
        return list(self._enrichers.values())
    
    async def enrich_entity(
        self, 
        entity: ONSITEntity,
        enricher_names: Optional[list[str]] = None
    ) -> list[ONSITEntity]:
        """
        Run all applicable enrichers on an entity.
        
        Args:
            entity: Entity to enrich
            enricher_names: Optional list of specific enrichers to use
            
        Returns:
            Combined list of all discovered entities
        """
        if enricher_names:
            enrichers = [
                self._enrichers[name] 
                for name in enricher_names 
                if name in self._enrichers
            ]
        else:
            enrichers = self.get_for_type(entity.entity_type)
        
        results = []
        for enricher in enrichers:
            entities = await enricher.safe_enrich(entity)
            results.extend(entities)
        
        return results


# Global registry instance
default_registry = EnricherRegistry()
