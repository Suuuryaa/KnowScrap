"""
KnowScraper - Sitemap Crawler
Discovers and parses sitemap.xml files.
Supports sitemap index files, gzipped sitemaps, and lastmod filtering.
"""

from __future__ import annotations

import gzip
import io
from datetime import datetime
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

NS = {
    "sm":  "http://www.sitemaps.org/schemas/sitemap/0.9",
    "img": "http://www.google.com/schemas/sitemap-image/1.1",
    "news":"http://www.google.com/schemas/sitemap-news/0.9",
}


async def fetch_sitemap_urls(
    base_url: str,
    *,
    modified_after: datetime | None = None,
    timeout: float = 15.0,
    max_urls: int | None = None,
) -> list[str]:
    """
    Discover all URLs from a site's sitemaps.
    Automatically follows sitemap index files.
    Filters by lastmod if modified_after is provided.

    Args:
        base_url: Site root URL e.g. "https://example.com"
        modified_after: Only return URLs modified after this date
        timeout: HTTP timeout in seconds
        max_urls: Cap on total URLs returned

    Returns:
        List of discovered URLs
    """
    sitemap_urls = await _discover_sitemaps(base_url, timeout=timeout)
    all_urls: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for sitemap_url in sitemap_urls:
            if max_urls and len(all_urls) >= max_urls:
                break
            try:
                urls = await _parse_sitemap(client, sitemap_url, modified_after=modified_after)
                all_urls.extend(urls)
            except Exception:
                continue

    if max_urls:
        all_urls = all_urls[:max_urls]

    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


async def _discover_sitemaps(base_url: str, *, timeout: float) -> list[str]:
    """Find sitemap locations from robots.txt and common paths."""
    found: list[str] = []
    base = base_url.rstrip("/")

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # Check robots.txt for Sitemap: directives
        try:
            resp = await client.get(f"{base}/robots.txt")
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        url = line.split(":", 1)[1].strip()
                        found.append(url)
        except Exception:
            pass

        # Fallback: try common sitemap paths
        if not found:
            for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"):
                try:
                    resp = await client.head(f"{base}{path}")
                    if resp.status_code == 200:
                        found.append(f"{base}{path}")
                        break
                except Exception:
                    continue

    return found or [f"{base}/sitemap.xml"]


async def _parse_sitemap(
    client: httpx.AsyncClient,
    url: str,
    *,
    modified_after: datetime | None = None,
) -> list[str]:
    """Parse a single sitemap or sitemap index. Recursively handles indexes."""
    resp = await client.get(url)
    if resp.status_code != 200:
        return []

    content = resp.content
    # Decompress gzipped sitemaps
    if url.endswith(".gz") or resp.headers.get("content-type", "").startswith("application/x-gzip"):
        content = gzip.decompress(content)

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    tag = root.tag.lower()

    # Sitemap index — recurse into child sitemaps
    if "sitemapindex" in tag:
        urls: list[str] = []
        for sitemap in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"):
            loc = sitemap.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc:
                child_urls = await _parse_sitemap(client, loc.strip(), modified_after=modified_after)
                urls.extend(child_urls)
        return urls

    # Regular sitemap — extract URLs
    urls = []
    for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        loc = url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if not loc:
            continue
        loc = loc.strip()

        # Apply lastmod filter
        if modified_after:
            lastmod_text = url_elem.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
            if lastmod_text:
                try:
                    lastmod = datetime.fromisoformat(lastmod_text.strip()[:10])
                    if lastmod < modified_after:
                        continue
                except ValueError:
                    pass

        urls.append(loc)

    return urls


async def discover_valid_sitemaps(base_url: str, timeout: float = 10.0) -> list[str]:
    """Return list of sitemap URLs that actually exist and respond 200."""
    candidates = await _discover_sitemaps(base_url, timeout=timeout)
    valid = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in candidates:
            try:
                resp = await client.head(url)
                if resp.status_code == 200:
                    valid.append(url)
            except Exception:
                continue
    return valid
