"""
ONSIT Discovery Orchestrator

Coordinates discovery scans by running crawlers and enrichers.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .models import (
    EntityType,
    ONSITEntity,
    Email,
    Domain,
    Username,
    Finding,
    ScanStatus,
    CrawlResult,
    create_entity,
)
from .crawler import ONSITCrawler, CrawlerConfig
from .extractors import IntelExtractor, extract_intel
from .enrichers import default_registry, EnricherRegistry


@dataclass
class DiscoveryScan:
    """Represents an active discovery scan."""
    scan_id: str
    seeds: list[ONSITEntity]
    enrichers: list[str]
    status: str = "pending"
    progress: float = 0.0
    findings: list[ONSITEntity] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ONSITOrchestrator:
    """
    Orchestrates ONSIT discovery scans.
    
    Coordinates:
    - Seed parsing (email, domain, username)
    - Enricher chain execution
    - Result aggregation
    - Progress tracking
    
    Usage:
        orchestrator = ONSITOrchestrator()
        scan_id = await orchestrator.start_discovery(["user@example.com"])
        status = await orchestrator.get_status(scan_id)
    """
    
    def __init__(self, registry: Optional[EnricherRegistry] = None):
        self.registry = registry or default_registry
        self._scans: dict[str, DiscoveryScan] = {}
        self._tasks: dict[str, asyncio.Task] = {}
    
    def parse_seed(self, seed: str) -> Optional[ONSITEntity]:
        """
        Parse a seed string into an entity.
        
        Args:
            seed: Raw seed string (email, domain, URL, username)
            
        Returns:
            Appropriate entity type, or None if unparsable
        """
        seed = seed.strip()
        
        # Email
        if "@" in seed and "." in seed.split("@")[1]:
            try:
                return Email(email=seed)
            except Exception:
                pass
        
        # URL -> Domain
        if seed.startswith("http://") or seed.startswith("https://"):
            try:
                from urllib.parse import urlparse
                hostname = urlparse(seed).hostname
                if hostname:
                    return Domain(domain=hostname)
            except Exception:
                pass
        
        # Domain
        if "." in seed and not " " in seed:
            try:
                return Domain(domain=seed)
            except Exception:
                pass
        
        # Username (default fallback)
        if seed and not " " in seed:
            return Username(username=seed)
        
        return None
    
    async def start_discovery(
        self,
        seeds: list[str],
        enrichers: Optional[list[str]] = None,
    ) -> str:
        """
        Start a discovery scan.
        
        Args:
            seeds: List of seed strings (emails, domains, usernames)
            enrichers: Optional list of specific enricher names to use
            
        Returns:
            Scan ID for tracking progress
        """
        scan_id = str(uuid.uuid4())[:8]
        
        # Parse seeds
        parsed_seeds = []
        for seed in seeds:
            entity = self.parse_seed(seed)
            if entity:
                parsed_seeds.append(entity)
        
        if not parsed_seeds:
            raise ValueError("No valid seeds provided")
        
        # Create scan record
        scan = DiscoveryScan(
            scan_id=scan_id,
            seeds=parsed_seeds,
            enrichers=enrichers or [],
            status="running",
            started_at=datetime.utcnow(),
        )
        self._scans[scan_id] = scan
        
        # Start background task
        task = asyncio.create_task(self._run_discovery(scan))
        self._tasks[scan_id] = task
        
        return scan_id
    
    async def _run_discovery(self, scan: DiscoveryScan) -> None:
        """Run the discovery process."""
        try:
            total_seeds = len(scan.seeds)
            processed = 0
            
            # Track all discovered entities
            discovered: list[ONSITEntity] = list(scan.seeds)
            seen_values: set[str] = set()
            
            # Process each seed
            for seed in scan.seeds:
                try:
                    # Run enrichers for this entity type
                    new_entities = await self.registry.enrich_entity(
                        seed,
                        scan.enrichers if scan.enrichers else None
                    )
                    
                    # Add unique entities
                    for entity in new_entities:
                        key = f"{entity.entity_type}:{entity.label}"
                        if key not in seen_values:
                            seen_values.add(key)
                            discovered.append(entity)
                            scan.findings.append(entity)
                    
                    # Recursive enrichment (one level)
                    for new_entity in new_entities:
                        more_entities = await self.registry.enrich_entity(
                            new_entity,
                            scan.enrichers if scan.enrichers else None
                        )
                        for entity in more_entities:
                            key = f"{entity.entity_type}:{entity.label}"
                            if key not in seen_values:
                                seen_values.add(key)
                                discovered.append(entity)
                                scan.findings.append(entity)
                
                except Exception as e:
                    scan.errors.append(f"Error processing {seed.label}: {str(e)}")
                
                processed += 1
                scan.progress = processed / total_seeds
            
            scan.status = "completed"
            scan.completed_at = datetime.utcnow()
            
        except Exception as e:
            scan.status = "failed"
            scan.errors.append(str(e))
            scan.completed_at = datetime.utcnow()
    
    async def get_status(self, scan_id: str) -> Optional[ScanStatus]:
        """Get status of a discovery scan."""
        scan = self._scans.get(scan_id)
        if not scan:
            return None
        
        return ScanStatus(
            scan_id=scan.scan_id,
            status=scan.status,
            progress=scan.progress,
            findings_count=len(scan.findings),
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            error="; ".join(scan.errors) if scan.errors else None,
        )
    
    async def get_findings(
        self, 
        scan_id: str,
        entity_type: Optional[EntityType] = None,
        limit: int = 100,
    ) -> list[ONSITEntity]:
        """
        Get findings from a discovery scan.
        
        Args:
            scan_id: Scan identifier
            entity_type: Optional filter by entity type
            limit: Maximum results to return
            
        Returns:
            List of discovered entities
        """
        scan = self._scans.get(scan_id)
        if not scan:
            return []
        
        findings = scan.findings
        
        if entity_type:
            findings = [f for f in findings if f.entity_type == entity_type]
        
        return findings[:limit]
    
    async def cancel_scan(self, scan_id: str) -> bool:
        """Cancel a running scan."""
        task = self._tasks.get(scan_id)
        if task and not task.done():
            task.cancel()
            scan = self._scans.get(scan_id)
            if scan:
                scan.status = "cancelled"
                scan.completed_at = datetime.utcnow()
            return True
        return False


# Global orchestrator instance
default_orchestrator = ONSITOrchestrator()
