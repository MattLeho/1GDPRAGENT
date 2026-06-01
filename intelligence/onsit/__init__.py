"""
ONSIT Package

OSINT discovery engine for the GDPR Intelligence Service.
"""

from .models import (
    EntityType,
    ONSITEntity,
    Domain,
    IP,
    Email,
    Username,
    SocialAccount,
    Breach,
    Finding,
    ScanStatus,
    CrawlResult,
    ENTITY_REGISTRY,
    create_entity,
)
from .extractors import (
    IntelExtractor,
    extract_intel,
    defang_url,
    refang_url,
)
from .crawler import (
    ONSITCrawler,
    CrawlerConfig,
    quick_crawl,
)
from .orchestrator import (
    ONSITOrchestrator,
    default_orchestrator,
)


__all__ = [
    # Models
    "EntityType",
    "ONSITEntity",
    "Domain",
    "IP",
    "Email",
    "Username",
    "SocialAccount",
    "Breach",
    "Finding",
    "ScanStatus",
    "CrawlResult",
    "ENTITY_REGISTRY",
    "create_entity",
    # Extractors
    "IntelExtractor",
    "extract_intel",
    "defang_url",
    "refang_url",
    # Crawler
    "ONSITCrawler",
    "CrawlerConfig",
    "quick_crawl",
    # Orchestrator
    "ONSITOrchestrator",
    "default_orchestrator",
]
