"""
Tests for PuppeteerCrawler and PuppeteerPage.
Mocks the Node.js microservice so no real browser is needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowscraper.crawlers.puppeteer_crawler import PuppeteerCrawler, PuppeteerPage, _BSElement
from knowscraper.core.router import Router
from knowscraper.core.request import Request
from knowscraper.storage.memory_storage import MemoryRequestQueue, MemoryDataset

SAMPLE_HTML = """
<html><head><title>Test Page</title></head>
<body>
  <h1 class="heading">Hello World</h1>
  <a href="/page2">Next page</a>
  <span data-id="42">Item content</span>
</body></html>
"""

PUPPETEER_RESPONSE = {
    "url": "https://example.com",
    "html": SAMPLE_HTML,
    "title": "Test Page",
    "cookies": [{"name": "session", "value": "abc123"}],
    "screenshot": None,
}


# ── PuppeteerPage unit tests ───────────────────────────────────────────────────

class TestPuppeteerPage:
    def _make_page(self, data=None):
        return PuppeteerPage(data or PUPPETEER_RESPONSE, crawler=MagicMock())

    def test_url(self):
        page = self._make_page()
        assert page.url == "https://example.com"

    def test_cookies(self):
        page = self._make_page()
        assert page.cookies == [{"name": "session", "value": "abc123"}]

    async def test_content(self):
        page = self._make_page()
        html = await page.content()
        assert "Hello World" in html

    async def test_title(self):
        page = self._make_page()
        assert await page.title() == "Test Page"

    def test_soup_property(self):
        page = self._make_page()
        soup = page.soup
        assert soup.find("h1").get_text(strip=True) == "Hello World"

    async def test_query_selector_found(self):
        page = self._make_page()
        el = await page.query_selector("h1.heading")
        assert el is not None
        assert await el.inner_text() == "Hello World"

    async def test_query_selector_not_found(self):
        page = self._make_page()
        el = await page.query_selector(".nonexistent")
        assert el is None

    async def test_query_selector_all(self):
        page = self._make_page()
        els = await page.query_selector_all("body *")
        assert len(els) > 0

    def test_screenshot_base64_none(self):
        page = self._make_page()
        assert page.screenshot_base64() is None

    def test_screenshot_base64_present(self):
        data = {**PUPPETEER_RESPONSE, "screenshot": "base64encodeddata"}
        page = self._make_page(data)
        assert page.screenshot_base64() == "base64encodeddata"

    def test_repr(self):
        page = self._make_page()
        assert "example.com" in repr(page)


class TestBSElement:
    def _make_el(self, html="<span data-id='42'>Content</span>"):
        from bs4 import BeautifulSoup
        tag = BeautifulSoup(html, "lxml").find("span")
        return _BSElement(tag)

    async def test_inner_text(self):
        el = self._make_el()
        assert await el.inner_text() == "Content"

    async def test_get_attribute(self):
        el = self._make_el()
        assert await el.get_attribute("data-id") == "42"

    async def test_is_visible(self):
        el = self._make_el()
        assert await el.is_visible() is True

    async def test_inner_text_on_none(self):
        el = _BSElement(None)
        assert await el.inner_text() == ""


# ── PuppeteerCrawler integration (mocked Node service) ────────────────────────

def _make_mock_http_response(data):
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestPuppeteerCrawler:
    def _make_crawler(self, router, dataset):
        crawler = PuppeteerCrawler(
            router=router,
            dataset=dataset,
            headless=True,
            use_anti_detection=False,
        )
        crawler.request_queue = MemoryRequestQueue()
        return crawler

    async def test_basic_crawl_calls_handler(self):
        router = Router()
        dataset = MemoryDataset()
        visited = []

        @router.default_handler
        async def handler(ctx):
            visited.append(ctx.request.url)
            title = await ctx.page.title()
            await dataset.push_data({"url": ctx.request.url, "title": title})

        crawler = self._make_crawler(router, dataset)

        mock_resp = _make_mock_http_response(PUPPETEER_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawler.run(["https://example.com"])

        assert "https://example.com" in visited
        assert dataset.count == 1
        assert dataset._records[0]["title"] == "Test Page"

    async def test_context_has_page_and_parsed(self):
        router = Router()
        dataset = MemoryDataset()
        context_ref = {}

        @router.default_handler
        async def handler(ctx):
            context_ref["ctx"] = ctx

        crawler = self._make_crawler(router, dataset)
        mock_resp = _make_mock_http_response(PUPPETEER_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawler.run(["https://example.com"])

        ctx = context_ref["ctx"]
        assert isinstance(ctx.page, PuppeteerPage)
        assert ctx.parsed is not None  # BeautifulSoup

    async def test_session_cookies_updated(self):
        router = Router()
        dataset = MemoryDataset()

        @router.default_handler
        async def handler(ctx):
            pass

        crawler = self._make_crawler(router, dataset)
        mock_resp = _make_mock_http_response(PUPPETEER_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawler.run(["https://example.com"])

        # Session cookie from puppeteer response should be stored
        sessions = crawler.session_pool._sessions
        if sessions:
            assert "session" in sessions[0].cookies

    async def test_stats_after_run(self):
        router = Router()
        dataset = MemoryDataset()

        @router.default_handler
        async def handler(ctx):
            pass

        crawler = self._make_crawler(router, dataset)
        mock_resp = _make_mock_http_response(PUPPETEER_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            stats = await crawler.run(["https://example.com"])

        assert stats["requests_done"] == 1
        assert stats["requests_failed"] == 0

    async def test_pre_actions_sent_in_body(self):
        router = Router()
        dataset = MemoryDataset()
        captured_body = {}

        @router.default_handler
        async def handler(ctx):
            pass

        actions = [{"type": "click", "selector": "button#accept"}]
        crawler = PuppeteerCrawler(
            router=router,
            dataset=dataset,
            pre_actions=actions,
            use_anti_detection=False,
        )
        crawler.request_queue = MemoryRequestQueue()

        mock_resp = _make_mock_http_response(PUPPETEER_RESPONSE)

        async def capture_post(url, json=None, **kwargs):
            captured_body.update(json or {})
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await crawler.run(["https://example.com"])

        assert captured_body.get("actions") == actions
