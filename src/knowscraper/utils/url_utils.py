"""KnowScraper - URL utilities."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag


def normalize_url(url: str, base_url: str = "") -> str | None:
    """Resolve relative URLs and normalize."""
    if not url or url.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    try:
        resolved = urljoin(base_url, url.strip())
        parsed = urlparse(resolved)
        # Strip fragment
        clean = urlunparse(parsed._replace(fragment=""))
        return clean if parsed.scheme in ("http", "https") else None
    except Exception:
        return None


def extract_links(soup: BeautifulSoup, selector: str = "a[href]", base_url: str = "") -> list[str]:
    """Extract all href links from a BeautifulSoup document."""
    links = []
    for tag in soup.select(selector):
        href = tag.get("href", "")
        url = normalize_url(href, base_url)
        if url:
            links.append(url)
    return links


def same_domain(url1: str, url2: str) -> bool:
    return urlparse(url1).netloc == urlparse(url2).netloc


def get_domain(url: str) -> str:
    return urlparse(url).netloc
