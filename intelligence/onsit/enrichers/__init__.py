"""
ONSIT Enrichers Package

Enrichers transform entities into new entities through external lookups.
"""

from .base import (
    BaseEnricher,
    EnricherRegistry,
    default_registry,
)
from .domain import (
    DNSResolutionEnricher,
    MXRecordEnricher,
    NSRecordEnricher,
    TXTRecordEnricher,
    WHOISEnricher,
    ReverseDNSEnricher,
    DOMAIN_ENRICHERS,
)
from .email import (
    GravatarEnricher,
    EmailToDomainEnricher,
    EmailValidationEnricher,
    EMAIL_ENRICHERS,
)
from .breach import (
    HIBPBreachEnricher,
    HIBPPasteEnricher,
    BREACH_ENRICHERS,
)
from .username import (
    MaigretEnricher,
    SimpleSocialEnricher,
    USERNAME_ENRICHERS,
)


# Register all enrichers with default registry
def register_all_enrichers(registry: EnricherRegistry = None):
    """Register all enrichers with a registry."""
    if registry is None:
        registry = default_registry
    
    all_enrichers = (
        DOMAIN_ENRICHERS +
        EMAIL_ENRICHERS +
        BREACH_ENRICHERS +
        USERNAME_ENRICHERS
    )
    
    for enricher_cls in all_enrichers:
        registry.register(enricher_cls())
    
    return registry


# Auto-register on import
register_all_enrichers()


__all__ = [
    # Base
    "BaseEnricher",
    "EnricherRegistry",
    "default_registry",
    "register_all_enrichers",
    # Domain
    "DNSResolutionEnricher",
    "MXRecordEnricher",
    "NSRecordEnricher",
    "TXTRecordEnricher",
    "WHOISEnricher",
    "ReverseDNSEnricher",
    "DOMAIN_ENRICHERS",
    # Email
    "GravatarEnricher",
    "EmailToDomainEnricher",
    "EmailValidationEnricher",
    "EMAIL_ENRICHERS",
    # Breach
    "HIBPBreachEnricher",
    "HIBPPasteEnricher",
    "BREACH_ENRICHERS",
    # Username
    "MaigretEnricher",
    "SimpleSocialEnricher",
    "USERNAME_ENRICHERS",
]
