"""
Domain Enrichers

Domain-related enrichment operations including:
- DNS Resolution (A, AAAA, MX, TXT, NS records)
- WHOIS Lookup
- Subdomain Discovery
- Reverse DNS

Uses dnspython for async DNS lookups.
Uses whoisdomain for WHOIS data.
"""

import asyncio
from typing import Optional
from datetime import datetime

import dns.asyncresolver
import dns.rdatatype
from dns.exception import DNSException

from .base import BaseEnricher
from ..models import (
    EntityType, 
    Domain, 
    IP, 
    Email,
    ONSITEntity,
)


class DNSResolutionEnricher(BaseEnricher):
    """
    Resolve domain to IP addresses via DNS.
    
    Input: Domain
    Output: IP addresses (A, AAAA records)
    """
    
    name = "dns_resolution"
    input_type = EntityType.DOMAIN
    output_types = [EntityType.IP]
    rate_limit = 0.1  # DNS is fast
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        domain = entity.domain if hasattr(entity, 'domain') else str(entity)
        
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 10
        
        # A records (IPv4)
        try:
            answers = await resolver.resolve(domain, "A")
            for rdata in answers:
                results.append(IP(
                    address=str(rdata),
                    version=4,
                    metadata={"record_type": "A", "domain": domain}
                ))
        except DNSException:
            pass
        
        # AAAA records (IPv6)
        try:
            answers = await resolver.resolve(domain, "AAAA")
            for rdata in answers:
                results.append(IP(
                    address=str(rdata),
                    version=6,
                    metadata={"record_type": "AAAA", "domain": domain}
                ))
        except DNSException:
            pass
        
        return results


class MXRecordEnricher(BaseEnricher):
    """
    Get mail servers for a domain.
    
    Input: Domain
    Output: Domains (mail servers)
    """
    
    name = "mx_records"
    input_type = EntityType.DOMAIN
    output_types = [EntityType.DOMAIN]
    rate_limit = 0.1
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        domain = entity.domain if hasattr(entity, 'domain') else str(entity)
        
        resolver = dns.asyncresolver.Resolver()
        
        try:
            answers = await resolver.resolve(domain, "MX")
            for rdata in answers:
                mx_host = str(rdata.exchange).rstrip(".")
                results.append(Domain(
                    domain=mx_host,
                    metadata={
                        "record_type": "MX",
                        "priority": rdata.preference,
                        "parent_domain": domain
                    }
                ))
        except DNSException:
            pass
        
        return results


class NSRecordEnricher(BaseEnricher):
    """
    Get nameservers for a domain.
    
    Input: Domain
    Output: Domains (nameservers)
    """
    
    name = "ns_records"
    input_type = EntityType.DOMAIN
    output_types = [EntityType.DOMAIN]
    rate_limit = 0.1
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        domain = entity.domain if hasattr(entity, 'domain') else str(entity)
        
        resolver = dns.asyncresolver.Resolver()
        
        try:
            answers = await resolver.resolve(domain, "NS")
            for rdata in answers:
                ns_host = str(rdata.target).rstrip(".")
                results.append(Domain(
                    domain=ns_host,
                    metadata={"record_type": "NS", "parent_domain": domain}
                ))
        except DNSException:
            pass
        
        return results


class TXTRecordEnricher(BaseEnricher):
    """
    Extract SPF, DKIM, DMARC and other TXT records.
    
    Input: Domain  
    Output: Domains, Emails (from SPF includes, DMARC rua/ruf)
    """
    
    name = "txt_records"
    input_type = EntityType.DOMAIN
    output_types = [EntityType.DOMAIN, EntityType.EMAIL]
    rate_limit = 0.1
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        domain = entity.domain if hasattr(entity, 'domain') else str(entity)
        
        resolver = dns.asyncresolver.Resolver()
        
        # Standard TXT
        try:
            answers = await resolver.resolve(domain, "TXT")
            for rdata in answers:
                txt_value = str(rdata).strip('"')
                
                # Parse SPF includes
                if txt_value.startswith("v=spf1"):
                    includes = self._parse_spf_includes(txt_value)
                    for inc in includes:
                        try:
                            results.append(Domain(
                                domain=inc,
                                metadata={"record_type": "SPF_INCLUDE", "parent": domain}
                            ))
                        except ValueError:
                            pass
        except DNSException:
            pass
        
        # DMARC
        try:
            answers = await resolver.resolve(f"_dmarc.{domain}", "TXT")
            for rdata in answers:
                txt_value = str(rdata).strip('"')
                emails = self._parse_dmarc_emails(txt_value)
                for email in emails:
                    results.append(Email(
                        email=email,
                        metadata={"record_type": "DMARC", "domain": domain}
                    ))
        except DNSException:
            pass
        
        return results
    
    def _parse_spf_includes(self, spf: str) -> list[str]:
        """Extract include domains from SPF record."""
        includes = []
        parts = spf.split()
        for part in parts:
            if part.startswith("include:"):
                includes.append(part.split(":", 1)[1])
            elif part.startswith("a:") or part.startswith("mx:"):
                includes.append(part.split(":", 1)[1])
        return includes
    
    def _parse_dmarc_emails(self, dmarc: str) -> list[str]:
        """Extract report emails from DMARC record."""
        emails = []
        import re
        # Match rua=mailto:xxx and ruf=mailto:xxx
        pattern = r"r[ua]f?=mailto:([^\s;]+)"
        matches = re.findall(pattern, dmarc, re.IGNORECASE)
        for match in matches:
            # Handle multiple emails separated by comma
            for email in match.split(","):
                email = email.strip()
                if "@" in email:
                    emails.append(email)
        return emails


class WHOISEnricher(BaseEnricher):
    """
    WHOIS lookup for domain registration info.
    
    Input: Domain
    Output: Updated Domain with WHOIS data, Emails
    
    Uses whoisdomain library (replaces deprecated python-whois).
    """
    
    name = "whois"
    input_type = EntityType.DOMAIN
    output_types = [EntityType.DOMAIN, EntityType.EMAIL]
    rate_limit = 2.0  # WHOIS servers rate limit aggressively
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        domain_name = entity.domain if hasattr(entity, 'domain') else str(entity)
        
        try:
            # Run sync WHOIS in executor
            import whoisdomain
            loop = asyncio.get_event_loop()
            whois_data = await loop.run_in_executor(
                None,
                lambda: whoisdomain.query(domain_name)
            )
            
            if whois_data:
                # Create enriched domain
                enriched = Domain(
                    domain=domain_name,
                    registrar=getattr(whois_data, 'registrar', None),
                    created_date=getattr(whois_data, 'creation_date', None),
                    expiry_date=getattr(whois_data, 'expiration_date', None),
                    metadata={
                        "whois_raw": str(whois_data),
                        "status": getattr(whois_data, 'status', None),
                        "name_servers": getattr(whois_data, 'name_servers', []),
                    }
                )
                results.append(enriched)
                
                # Extract emails from WHOIS
                emails = getattr(whois_data, 'emails', []) or []
                if isinstance(emails, str):
                    emails = [emails]
                for email in emails:
                    if "@" in str(email):
                        results.append(Email(
                            email=str(email),
                            metadata={"source": "whois", "domain": domain_name}
                        ))
                        
        except Exception:
            pass
        
        return results


class ReverseDNSEnricher(BaseEnricher):
    """
    Reverse DNS lookup (PTR records).
    
    Input: IP
    Output: Domain
    """
    
    name = "reverse_dns"
    input_type = EntityType.IP
    output_types = [EntityType.DOMAIN]
    rate_limit = 0.1
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        ip_address = entity.address if hasattr(entity, 'address') else str(entity)
        
        resolver = dns.asyncresolver.Resolver()
        
        try:
            # Create reverse DNS name
            from dns.reversename import from_address
            reverse_name = from_address(ip_address)
            
            answers = await resolver.resolve(reverse_name, "PTR")
            for rdata in answers:
                hostname = str(rdata.target).rstrip(".")
                results.append(Domain(
                    domain=hostname,
                    metadata={"ptr_record": True, "ip": ip_address}
                ))
        except (DNSException, Exception):
            pass
        
        return results


# All domain-related enrichers
DOMAIN_ENRICHERS = [
    DNSResolutionEnricher,
    MXRecordEnricher,
    NSRecordEnricher,
    TXTRecordEnricher,
    WHOISEnricher,
    ReverseDNSEnricher,
]
