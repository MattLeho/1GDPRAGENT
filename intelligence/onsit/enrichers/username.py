"""
Username Enricher

Username search across social platforms using Maigret.
Source: https://github.com/soxoj/maigret
"""

import asyncio
import subprocess
import json
from typing import Optional

import aiohttp

from .base import BaseEnricher
from ..models import (
    EntityType,
    Username,
    SocialAccount,
    ONSITEntity,
)


class MaigretEnricher(BaseEnricher):
    """
    Search for username across 3000+ social platforms using Maigret.
    
    Input: Username
    Output: SocialAccount records
    
    Requires maigret to be installed: pip install maigret
    """
    
    name = "maigret"
    input_type = EntityType.USERNAME
    output_types = [EntityType.SOCIAL_ACCOUNT]
    rate_limit = 5.0  # Maigret makes many requests internally
    timeout = 120  # Username searches can take time
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        username = entity.username if hasattr(entity, 'username') else str(entity)
        
        try:
            # Run maigret in subprocess with JSON output
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: self._run_maigret(username)
            )
            
            if output:
                results.extend(output)
                
        except Exception:
            pass
        
        return results
    
    def _run_maigret(self, username: str) -> list[SocialAccount]:
        """Run maigret CLI and parse results."""
        results = []
        
        try:
            # Run with limited sites for speed (top 100)
            process = subprocess.run(
                [
                    "maigret", username,
                    "--json", "simple",
                    "--timeout", "10",
                    "--top-sites", "100",
                    "--no-recursion",
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
            
            if process.returncode == 0:
                # Parse JSON output
                lines = process.stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("{"):
                        try:
                            data = json.loads(line)
                            for site_name, site_data in data.items():
                                if site_data.get("status") == "Claimed":
                                    results.append(SocialAccount(
                                        platform=site_name.lower(),
                                        username=username,
                                        url=site_data.get("url_user"),
                                        metadata={
                                            "tags": site_data.get("tags", []),
                                            "status": site_data.get("status"),
                                        }
                                    ))
                        except json.JSONDecodeError:
                            pass
                            
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Maigret not installed
            pass
        except Exception:
            pass
        
        return results


class SimpleSocialEnricher(BaseEnricher):
    """
    Quick check for username on major platforms (no external deps).
    
    Input: Username
    Output: SocialAccount records
    
    Checks common platforms by URL pattern.
    """
    
    name = "simple_social"
    input_type = EntityType.USERNAME
    output_types = [EntityType.SOCIAL_ACCOUNT]
    rate_limit = 0.5
    
    # Major platforms with predictable URL patterns
    PLATFORMS = {
        "github": "https://github.com/{username}",
        "twitter": "https://twitter.com/{username}",
        "instagram": "https://instagram.com/{username}",
        "linkedin": "https://linkedin.com/in/{username}",
        "facebook": "https://facebook.com/{username}",
        "tiktok": "https://tiktok.com/@{username}",
        "youtube": "https://youtube.com/@{username}",
        "reddit": "https://reddit.com/user/{username}",
        "pinterest": "https://pinterest.com/{username}",
        "medium": "https://medium.com/@{username}",
    }
    
    async def enrich(self, entity: ONSITEntity) -> list[ONSITEntity]:
        results = []
        username = entity.username if hasattr(entity, 'username') else str(entity)
        
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for platform, url_template in self.PLATFORMS.items():
                url = url_template.format(username=username)
                tasks.append(self._check_profile(session, platform, url, username))
            
            checked = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in checked:
                if isinstance(result, SocialAccount):
                    results.append(result)
        
        return results
    
    async def _check_profile(
        self, 
        session: aiohttp.ClientSession, 
        platform: str, 
        url: str,
        username: str
    ) -> Optional[SocialAccount]:
        """Check if profile exists."""
        try:
            async with session.head(
                url, 
                timeout=5,
                allow_redirects=True
            ) as response:
                # 200 = profile exists
                if response.status == 200:
                    return SocialAccount(
                        platform=platform,
                        username=username,
                        url=url,
                        metadata={"verified_by": "head_request"}
                    )
        except Exception:
            pass
        
        return None


# All username-related enrichers
USERNAME_ENRICHERS = [
    MaigretEnricher,
    SimpleSocialEnricher,
]
