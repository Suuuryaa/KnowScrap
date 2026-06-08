"""
KnowScraper - robots.txt enforcement
Fetches, caches, and checks robots.txt before each request.
Integrated into BaseCrawler when respect_robots_txt=True.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

_cache: dict[str, RobotFileParser] = {}
_fetch_lock = asyncio.Lock()


async def fetch_robots(base_url: str, timeout: float = 5.0) -> RobotFileParser:
    """Fetch and parse robots.txt for a domain. Cached per domain."""
    async with _fetch_lock:
        if base_url in _cache:
            return _cache[base_url]

        rp = RobotFileParser()
        rp.set_url(f"{base_url}/robots.txt")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{base_url}/robots.txt", follow_redirects=True)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.allow_all = True
        except Exception:
            rp.allow_all = True

        _cache[base_url] = rp
        return rp


async def can_fetch(url: str, user_agent: str = "KnowScraperBot") -> bool:
    """
    Return True if robots.txt allows fetching this URL.
    Fails open — returns True if robots.txt cannot be fetched.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = await fetch_robots(base)
    return rp.can_fetch(user_agent, url)


async def get_crawl_delay(url: str, user_agent: str = "KnowScraperBot") -> float | None:
    """Return the Crawl-delay directive from robots.txt, or None if not set."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = await fetch_robots(base)
    delay = rp.crawl_delay(user_agent) or rp.crawl_delay("*")
    return float(delay) if delay else None


def clear_cache() -> None:
    """Clear the robots.txt cache — useful for testing."""
    _cache.clear()
