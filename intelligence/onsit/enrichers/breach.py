"""
Breach Enricher

Check email addresses against HaveIBeenPwned API.
"""

import asyncio
from typing import Optional

import aiohttp

from .base import BaseEnricher
from ..models import (
    EntityType,
    Email,
    Breach,
    ONSITEntity,
)


class HIBPBreachEnricher(BaseEnricher):
    """
    Check email against HaveIBeenPwned API.
    
    Input: Email
    Output: Breach records
    
    Note: HIBP requires an API key for breach data.
    Free rate-limited access available for password checking.
    """
    
    name = "hibp_breach"
    input_type = EntityType.EMAIL
    output_types = [EntityType.BREACH]
    rate_limit = 1.5  # HIBP rate limit: 10 per minute
    requires_api_key = True
    api_key_name = "HIBP_API_KEY"
    
    HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        email = entity.email if hasattr(entity, 'email') else str(entity)
        
        if not self.api_key:
            return results
        
        headers = {
            "hibp-api-key": self.api_key,
            "User-Agent": "ONSIT-GDPR-Tool",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.HIBP_API_URL}/breachedaccount/{email}"
                
                async with session.get(
                    url, 
                    headers=headers,
                    params={"truncateResponse": "false"},
                    timeout=10
                ) as response:
                    
                    if response.status == 200:
                        breaches = await response.json()
                        
                        for breach_data in breaches:
                            breach = Breach(
                                name=breach_data.get("Name", "Unknown"),
                                breach_date=self._parse_date(
                                    breach_data.get("BreachDate")
                                ),
                                description=breach_data.get("Description"),
                                data_classes=breach_data.get("DataClasses", []),
                                is_verified=breach_data.get("IsVerified", False),
                                pwn_count=breach_data.get("PwnCount"),
                                metadata={
                                    "domain": breach_data.get("Domain"),
                                    "logo_path": breach_data.get("LogoPath"),
                                    "is_sensitive": breach_data.get("IsSensitive"),
                                    "is_retired": breach_data.get("IsRetired"),
                                    "is_spam_list": breach_data.get("IsSpamList"),
                                    "is_fabricated": breach_data.get("IsFabricated"),
                                    "email": email,
                                }
                            )
                            results.append(breach)
                    
                    elif response.status == 404:
                        # No breaches found - good news!
                        pass
                    
        except Exception:
            pass
        
        return results
    
    def _parse_date(self, date_str: Optional[str]):
        """Parse HIBP date format."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


class HIBPPasteEnricher(BaseEnricher):
    """
    Check email against HaveIBeenPwned Pastes API.
    
    Input: Email
    Output: Breach records (from pastes)
    """
    
    name = "hibp_paste"
    input_type = EntityType.EMAIL
    output_types = [EntityType.BREACH]
    rate_limit = 1.5
    requires_api_key = True
    api_key_name = "HIBP_API_KEY"
    
    HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        email = entity.email if hasattr(entity, 'email') else str(entity)
        
        if not self.api_key:
            return results
        
        headers = {
            "hibp-api-key": self.api_key,
            "User-Agent": "ONSIT-GDPR-Tool",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.HIBP_API_URL}/pasteaccount/{email}"
                
                async with session.get(
                    url,
                    headers=headers,
                    timeout=10
                ) as response:
                    
                    if response.status == 200:
                        pastes = await response.json()
                        
                        for paste in pastes:
                            breach = Breach(
                                name=f"Paste: {paste.get('Source', 'Unknown')}",
                                breach_date=self._parse_date(paste.get("Date")),
                                description=paste.get("Title"),
                                data_classes=["Email", "Password"],
                                is_verified=False,
                                pwn_count=paste.get("EmailCount"),
                                metadata={
                                    "paste_id": paste.get("Id"),
                                    "source": paste.get("Source"),
                                    "email": email,
                                }
                            )
                            results.append(breach)
                            
        except Exception:
            pass
        
        return results
    
    def _parse_date(self, date_str: Optional[str]):
        """Parse ISO date format."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None


# All breach-related enrichers
BREACH_ENRICHERS = [
    HIBPBreachEnricher,
    HIBPPasteEnricher,
]
