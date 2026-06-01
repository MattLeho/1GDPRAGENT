"""
ONSIT Async Web Crawler

Photon-inspired async crawler with:
- aiohttp for high-concurrency HTTP
- asyncio.Semaphore for rate limiting
- robots.txt compliance
- Configurable depth and delay

Source patterns: https://github.com/s0md3v/Photon
"""

import asyncio
import re
from typing import Optional
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from .models import CrawlResult, Finding
from .extractors import IntelExtractor


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class CrawlerConfig:
    """Crawler configuration options."""
    max_depth: int = 2
    max_pages: int = 100
    concurrent_requests: int = 10
    request_delay: float = 0.5  # seconds between requests per domain
    timeout: int = 30
    respect_robots: bool = True
    user_agent: str = "ONSIT-Crawler/1.0 (GDPR Compliance Tool)"
    follow_external: bool = False
    extract_intel: bool = True
    allowed_content_types: list[str] = field(default_factory=lambda: [
        "text/html",
        "application/xhtml+xml",
    ])


# =============================================================================
# User Agent Rotation (from Photon patterns)
# =============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# =============================================================================
# Robots.txt Parser
# =============================================================================

class RobotsParser:
    """Simple robots.txt parser."""
    
    def __init__(self):
        self._cache: dict[str, dict] = {}
    
    async def fetch(self, session: aiohttp.ClientSession, base_url: str) -> dict:
        """Fetch and parse robots.txt for a domain."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        if robots_url in self._cache:
            return self._cache[robots_url]
        
        rules = {"disallowed": [], "crawl_delay": 0}
        
        try:
            async with session.get(robots_url, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    rules = self._parse(text)
        except Exception:
            pass
        
        self._cache[robots_url] = rules
        return rules
    
    def _parse(self, text: str) -> dict:
        """Parse robots.txt content."""
        rules = {"disallowed": [], "crawl_delay": 0}
        current_agent = None
        
        for line in text.split("\n"):
            line = line.strip().lower()
            
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agent = agent in ("*", "onsit-crawler")
            
            elif current_agent and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    rules["disallowed"].append(path)
            
            elif current_agent and line.startswith("crawl-delay:"):
                try:
                    rules["crawl_delay"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        
        return rules
    
    def is_allowed(self, url: str, rules: dict) -> bool:
        """Check if URL is allowed by robots.txt rules."""
        parsed = urlparse(url)
        path = parsed.path or "/"
        
        for disallowed in rules.get("disallowed", []):
            if path.startswith(disallowed):
                return False
        
        return True


# =============================================================================
# Main Crawler Class
# =============================================================================

class ONSITCrawler:
    """
    Async web crawler for ONSIT discovery.
    
    Features:
    - Multi-level recursive crawling (configurable depth)
    - Rate limiting with asyncio.Semaphore
    - robots.txt compliance
    - Intel extraction on each page
    - URL deduplication
    
    Usage:
        crawler = ONSITCrawler(config)
        result = await crawler.crawl("https://example.com")
    """
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self.extractor = IntelExtractor()
        self.robots = RobotsParser()
        
        # Crawl state
        self._visited: set[str] = set()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._domain_delays: dict[str, datetime] = {}
        
        # Results
        self._internal_urls: set[str] = set()
        self._external_urls: set[str] = set()
        self._files: list[str] = []
        self._scripts: list[str] = []
        self._intel: list[Finding] = []
    
    async def crawl(self, start_url: str) -> CrawlResult:
        """
        Start crawling from a URL.
        
        Args:
            start_url: Starting URL
            
        Returns:
            CrawlResult with collected data
        """
        # Reset state
        self._visited.clear()
        self._internal_urls.clear()
        self._external_urls.clear()
        self._files.clear()
        self._scripts.clear()
        self._intel.clear()
        
        self._semaphore = asyncio.Semaphore(self.config.concurrent_requests)
        
        # Parse base domain
        parsed = urlparse(start_url)
        base_domain = parsed.netloc
        
        connector = aiohttp.TCPConnector(limit=self.config.concurrent_requests)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": self.config.user_agent}
        ) as session:
            
            # Fetch robots.txt if enabled
            robots_rules = {}
            if self.config.respect_robots:
                robots_rules = await self.robots.fetch(session, start_url)
                if robots_rules.get("crawl_delay", 0) > 0:
                    self.config.request_delay = max(
                        self.config.request_delay, 
                        robots_rules["crawl_delay"]
                    )
            
            # Start with seed URL
            await self._queue.put((start_url, 0))
            
            # Process queue
            while not self._queue.empty() and len(self._visited) < self.config.max_pages:
                url, depth = await self._queue.get()
                
                if url in self._visited:
                    continue
                
                if depth > self.config.max_depth:
                    continue
                
                # Check robots.txt
                if self.config.respect_robots and not self.robots.is_allowed(url, robots_rules):
                    continue
                
                self._visited.add(url)
                
                # Crawl page
                await self._crawl_page(session, url, depth, base_domain)
        
        return CrawlResult(
            url=start_url,
            status_code=200,
            internal_urls=list(self._internal_urls),
            external_urls=list(self._external_urls),
            intel=self._intel,
            files=self._files,
            scripts=self._scripts,
        )
    
    async def _crawl_page(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        depth: int,
        base_domain: str
    ) -> None:
        """Crawl a single page."""
        async with self._semaphore:
            # Rate limiting per domain
            await self._apply_delay(base_domain)
            
            try:
                async with session.get(url) as response:
                    content_type = response.headers.get("Content-Type", "")
                    
                    # Check content type
                    if not any(ct in content_type for ct in self.config.allowed_content_types):
                        # Track files
                        if self._is_file_url(url):
                            self._files.append(url)
                        return
                    
                    html = await response.text()
                    
                    # Extract intel
                    if self.config.extract_intel:
                        findings = self.extractor.extract_all(html, source=url)
                        self._intel.extend(findings)
                    
                    # Parse links
                    await self._extract_links(html, url, depth, base_domain)
                    
            except asyncio.TimeoutError:
                pass
            except aiohttp.ClientError:
                pass
            except Exception:
                pass
    
    async def _extract_links(
        self, 
        html: str, 
        base_url: str, 
        depth: int,
        base_domain: str
    ) -> None:
        """Extract and categorize links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        
        # Extract all hrefs
        for tag in soup.find_all(["a", "link"], href=True):
            href = tag.get("href", "")
            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)
            
            # Skip non-HTTP
            if parsed.scheme not in ("http", "https"):
                continue
            
            # Normalize URL
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                normalized += f"?{parsed.query}"
            
            # Categorize
            if parsed.netloc == base_domain:
                self._internal_urls.add(normalized)
                
                # Queue for crawling if not visited
                if normalized not in self._visited and depth < self.config.max_depth:
                    await self._queue.put((normalized, depth + 1))
            else:
                self._external_urls.add(normalized)
        
        # Extract scripts
        for tag in soup.find_all("script", src=True):
            src = tag.get("src", "")
            absolute_src = urljoin(base_url, src)
            self._scripts.append(absolute_src)
    
    async def _apply_delay(self, domain: str) -> None:
        """Apply rate limiting delay per domain."""
        now = datetime.utcnow()
        
        if domain in self._domain_delays:
            last = self._domain_delays[domain]
            elapsed = (now - last).total_seconds()
            
            if elapsed < self.config.request_delay:
                await asyncio.sleep(self.config.request_delay - elapsed)
        
        self._domain_delays[domain] = datetime.utcnow()
    
    def _is_file_url(self, url: str) -> bool:
        """Check if URL points to a downloadable file."""
        file_extensions = (
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", 
            ".zip", ".rar", ".tar", ".gz",
            ".jpg", ".jpeg", ".png", ".gif", ".svg",
            ".mp3", ".mp4", ".avi", ".mov",
        )
        return url.lower().endswith(file_extensions)


# =============================================================================
# Convenience Functions
# =============================================================================

async def quick_crawl(url: str, depth: int = 1, max_pages: int = 10) -> CrawlResult:
    """Quick crawl with minimal configuration."""
    config = CrawlerConfig(
        max_depth=depth,
        max_pages=max_pages,
        concurrent_requests=5,
    )
    crawler = ONSITCrawler(config)
    return await crawler.crawl(url)


async def extract_intel_from_url(url: str) -> list[Finding]:
    """Fetch a single URL and extract intel."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            return IntelExtractor().extract_all(html, source=url)
