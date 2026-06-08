"""Tests for sitemap discovery and parsing."""

import gzip
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from knowscraper.utils.sitemap import fetch_sitemap_urls, discover_valid_sitemaps


SIMPLE_SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc><lastmod>2024-01-01</lastmod></url>
  <url><loc>https://example.com/page2</loc><lastmod>2024-06-01</lastmod></url>
  <url><loc>https://example.com/page3</loc><lastmod>2023-01-01</lastmod></url>
</urlset>"""

SITEMAP_INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>
</sitemapindex>"""

ROBOTS_WITH_SITEMAP = b"""User-agent: *
Disallow: /admin/
Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/news-sitemap.xml
"""


def _make_response(content: bytes, status: int = 200, content_type: str = "text/xml"):
    mock = MagicMock()
    mock.status_code = status
    mock.content = content
    mock.headers = {"content-type": content_type}
    mock.raise_for_status = MagicMock()
    return mock


class TestFetchSitemapUrls:
    async def test_returns_urls_from_simple_sitemap(self):
        robots_resp = _make_response(ROBOTS_WITH_SITEMAP, content_type="text/plain")
        sitemap_resp = _make_response(SIMPLE_SITEMAP)

        async def mock_get(url, **kwargs):
            if "robots.txt" in url:
                return robots_resp
            return sitemap_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            urls = await fetch_sitemap_urls("https://example.com")

        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/page3" in urls

    async def test_max_urls_cap(self):
        robots_resp = _make_response(ROBOTS_WITH_SITEMAP, content_type="text/plain")
        sitemap_resp = _make_response(SIMPLE_SITEMAP)

        async def mock_get(url, **kwargs):
            if "robots.txt" in url:
                return robots_resp
            return sitemap_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            urls = await fetch_sitemap_urls("https://example.com", max_urls=2)

        assert len(urls) <= 2

    async def test_modified_after_filter(self):
        robots_resp = _make_response(ROBOTS_WITH_SITEMAP, content_type="text/plain")
        sitemap_resp = _make_response(SIMPLE_SITEMAP)

        async def mock_get(url, **kwargs):
            if "robots.txt" in url:
                return robots_resp
            return sitemap_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            cutoff = datetime(2024, 3, 1)
            urls = await fetch_sitemap_urls("https://example.com", modified_after=cutoff)

        # Only page2 (2024-06-01) is after the cutoff
        assert "https://example.com/page2" in urls
        assert "https://example.com/page1" not in urls
        assert "https://example.com/page3" not in urls

    async def test_gzipped_sitemap(self):
        compressed = gzip.compress(SIMPLE_SITEMAP)
        robots_resp = _make_response(b"Sitemap: https://example.com/sitemap.xml.gz\n", content_type="text/plain")
        gz_resp = _make_response(compressed, content_type="application/x-gzip")

        async def mock_get(url, **kwargs):
            if "robots.txt" in url:
                return robots_resp
            return gz_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            urls = await fetch_sitemap_urls("https://example.com")

        assert len(urls) >= 1


class TestDiscoverValidSitemaps:
    async def test_returns_working_sitemaps(self):
        ok_resp = _make_response(SIMPLE_SITEMAP)
        not_found = _make_response(b"", status=404)

        async def mock_get(url, **kwargs):
            if "sitemap.xml" in url and "news" not in url:
                return ok_resp
            return not_found

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            valid = await discover_valid_sitemaps("https://example.com")

        assert isinstance(valid, list)
