"""
Email Enrichers

Email-related enrichment operations including:
- Gravatar lookup
- Email validation (MX check)
- Email to domain extraction

"""

import asyncio
import hashlib
from typing import Optional

import aiohttp

from .base import BaseEnricher
from ..models import (
    EntityType,
    Email,
    Domain,
    Gravatar,
    ONSITEntity,
)


class GravatarEnricher(BaseEnricher):
    """
    Lookup Gravatar profile for email.
    
    Input: Email
    Output: Gravatar profile
    """
    
    name = "gravatar"
    input_type = EntityType.EMAIL
    output_types = [EntityType.GRAVATAR]
    rate_limit = 0.5
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        email = entity.email if hasattr(entity, 'email') else str(entity)
        
        # Generate MD5 hash
        email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
        profile_url = f"https://www.gravatar.com/{email_hash}.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(profile_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "entry" in data and len(data["entry"]) > 0:
                            entry = data["entry"][0]
                            
                            gravatar = Gravatar(
                                email_hash=email_hash,
                                display_name=entry.get("displayName"),
                                profile_url=f"https://www.gravatar.com/{email_hash}",
                                avatar_url=entry.get("thumbnailUrl"),
                                metadata={
                                    "name": entry.get("name", {}),
                                    "location": entry.get("currentLocation"),
                                    "about": entry.get("aboutMe"),
                                    "urls": entry.get("urls", []),
                                    "photos": entry.get("photos", []),
                                    "accounts": entry.get("accounts", []),
                                }
                            )
                            results.append(gravatar)
        except Exception:
            pass
        
        return results


class EmailToDomainEnricher(BaseEnricher):
    """
    Extract domain from email address.
    
    Input: Email
    Output: Domain
    """
    
    name = "email_to_domain"
    input_type = EntityType.EMAIL
    output_types = [EntityType.DOMAIN]
    rate_limit = 0.0  # No external calls
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        email = entity.email if hasattr(entity, 'email') else str(entity)
        
        if "@" in email:
            domain_part = email.split("@")[1]
            try:
                results.append(Domain(
                    domain=domain_part,
                    metadata={"extracted_from_email": email}
                ))
            except ValueError:
                pass
        
        return results


class EmailValidationEnricher(BaseEnricher):
    """
    Validate email by checking MX records.
    
    Input: Email
    Output: Email with validation status
    """
    
    name = "email_validation"
    input_type = EntityType.EMAIL
    output_types = [EntityType.EMAIL]
    rate_limit = 0.2
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        email_addr = entity.email if hasattr(entity, 'email') else str(entity)
        
        if "@" not in email_addr:
            return results
        
        domain = email_addr.split("@")[1]
        
        try:
            import dns.asyncresolver
            from dns.exception import DNSException
            
            resolver = dns.asyncresolver.Resolver()
            answers = await resolver.resolve(domain, "MX")
            
            # If we got MX records, domain can receive email
            has_mx = len(list(answers)) > 0
            
            validated = Email(
                email=email_addr,
                verified=has_mx,
                provider=domain,
                metadata={
                    "mx_count": len(list(answers)) if has_mx else 0,
                    "validation_source": "mx_check"
                }
            )
            results.append(validated)
            
        except DNSException:
            # No MX records - still create result
            validated = Email(
                email=email_addr,
                verified=False,
                provider=domain,
                metadata={"validation_error": "no_mx_records"}
            )
            results.append(validated)
        except Exception:
            pass
        
        return results


# All email-related enrichers
EMAIL_ENRICHERS = [
    GravatarEnricher,
    EmailToDomainEnricher,
    EmailValidationEnricher,
]
