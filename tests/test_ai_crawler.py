"""
Tests for AICrawler and AICrawlingContext.
Mocks the Anthropic API so no API key is needed.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowscraper.crawlers.ai_crawler import AICrawler, AICrawlingContext
from knowscraper.core.router import CrawlingContext, Router
from knowscraper.core.request import Request
from knowscraper.storage.memory_storage import MemoryDataset, MemoryRequestQueue

SAMPLE_HTML = """
<html><head><title>Product Page</title></head>
<body>
  <h1 class="product-name">Awesome Widget</h1>
  <span class="price">$29.99</span>
  <span class="rating">4.5 stars</span>
  <button id="add-to-cart">Add to Cart</button>
  <input type="text" id="search" placeholder="Search...">
</body></html>
"""

FAKE_API_KEY = "sk-ant-test-key-123"


def _claude_response(content: str):
    """Build a fake Anthropic API response dict."""
    return {"content": [{"text": content}]}


def _make_ai_context(html=SAMPLE_HTML, page=None):
    request = Request(url="https://example.com")
    ctx = AICrawlingContext(
        request=request,
        response={"body": html, "status": 200},
        parsed=None,
        page=page,
        crawler=MagicMock(),
        session=MagicMock(cookies={}),
        proxy_info=None,
        log=MagicMock(),
        api_key=FAKE_API_KEY,
        model="claude-haiku-4-5-20251001",
    )
    return ctx


# ── AICrawlingContext tests ───────────────────────────────────────────────────

class TestAICrawlingContext:
    async def test_extract_returns_dict(self):
        ctx = _make_ai_context()
        extracted_data = {"name": "Awesome Widget", "price": "$29.99", "rating": "4.5 stars"}

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(json.dumps(extracted_data))
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.extract("product name, price, rating")

        assert result["name"] == "Awesome Widget"
        assert result["price"] == "$29.99"

    async def test_extract_with_schema(self):
        ctx = _make_ai_context()
        schema = {"name": "string", "price": "string"}
        extracted_data = {"name": "Awesome Widget", "price": "$29.99"}

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(json.dumps(extracted_data))
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.extract("product info", schema=schema)

        assert isinstance(result, dict)

    async def test_extract_handles_json_in_markdown_block(self):
        ctx = _make_ai_context()
        response_text = "```json\n{\"name\": \"Widget\"}\n```"

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(response_text)
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.extract("product name")

        assert result.get("name") == "Widget"

    async def test_extract_handles_invalid_json_gracefully(self):
        ctx = _make_ai_context()

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response("Sorry, I can't extract that.")
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.extract("something")

        assert "_parse_error" in result

    async def test_act_requires_browser(self):
        ctx = _make_ai_context(page=None)
        with pytest.raises(RuntimeError, match="act\\(\\) requires a browser crawler"):
            await ctx.act("click login")

    async def test_act_with_playwright_page(self):
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=SAMPLE_HTML)
        mock_page.click = AsyncMock()

        ctx = _make_ai_context(page=mock_page)
        action_json = json.dumps({"selector": "#add-to-cart", "action": "click"})

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(action_json)
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.act("click the add to cart button")

        assert result is True
        mock_page.click.assert_called_once_with("#add-to-cart")

    async def test_act_type_action(self):
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=SAMPLE_HTML)
        mock_page.fill = AsyncMock()

        ctx = _make_ai_context(page=mock_page)
        action_json = json.dumps({"selector": "#search", "action": "type", "text": "hello world"})

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(action_json)
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.act("type 'hello world' into search")

        assert result is True
        mock_page.fill.assert_called_once_with("#search", "hello world")

    async def test_act_returns_false_when_no_selector(self):
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=SAMPLE_HTML)

        ctx = _make_ai_context(page=mock_page)
        action_json = json.dumps({"selector": None, "action": None})

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(action_json)
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.act("do something impossible")

        assert result is False

    async def test_observe_returns_list(self):
        ctx = _make_ai_context()
        elements = [
            {"description": "Add to Cart button", "selector": "#add-to-cart", "action": "click"},
            {"description": "Search input", "selector": "#search", "action": "type"},
        ]

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response(json.dumps(elements))
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await ctx.observe()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["selector"] == "#add-to-cart"

    async def test_get_page_html_from_response(self):
        ctx = _make_ai_context()
        html = await ctx._get_page_html()
        assert "Awesome Widget" in html

    async def test_get_page_html_from_playwright_page(self):
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value=SAMPLE_HTML)
        ctx = _make_ai_context(page=mock_page)
        html = await ctx._get_page_html()
        assert "Awesome Widget" in html

    async def test_large_html_truncated(self):
        """Very large pages should be truncated before sending to Claude."""
        big_html = "<html><body>" + "<p>Content</p>" * 5000 + "</body></html>"
        ctx = _make_ai_context(html=big_html)

        sent_prompts = []

        mock_resp = MagicMock()
        mock_resp.json.return_value = _claude_response('{"name": "test"}')
        mock_resp.raise_for_status = MagicMock()

        async def capture_post(url, json=None, **kwargs):
            if json:
                sent_prompts.append(json["messages"][0]["content"])
            return mock_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await ctx.extract("product name")

        # The prompt should exist and not be enormous
        assert len(sent_prompts) == 1
        assert len(sent_prompts[0]) < 120_000


# ── AICrawler constructor tests ───────────────────────────────────────────────

class TestAICrawlerInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="Anthropic API key required"):
            AICrawler()

    def test_accepts_explicit_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        router = Router()
        crawler = AICrawler(api_key=FAKE_API_KEY, router=router, use_browser=False)
        assert crawler._api_key == FAKE_API_KEY

    def test_reads_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
        router = Router()
        crawler = AICrawler(router=router, use_browser=False)
        assert crawler._api_key == "sk-ant-from-env"

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_API_KEY)
        router = Router()
        crawler = AICrawler(router=router, use_browser=False)
        assert "haiku" in crawler._model

    def test_custom_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_API_KEY)
        router = Router()
        crawler = AICrawler(
            router=router,
            model="claude-sonnet-4-6",
            use_browser=False,
        )
        assert crawler._model == "claude-sonnet-4-6"


# ── AICrawler end-to-end (mocked) ────────────────────────────────────────────

class TestAICrawlerRun:
    async def test_browser_mode_wraps_context_in_ai_context(self, monkeypatch):
        """AICrawler wraps PlaywrightCrawler context in AICrawlingContext."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_API_KEY)

        router = Router()
        dataset = MemoryDataset()
        context_type_seen = []

        @router.default_handler
        async def handler(ctx):
            context_type_seen.append(type(ctx).__name__)

        crawler = AICrawler(
            router=router,
            dataset=dataset,
            api_key=FAKE_API_KEY,
            use_browser=True,
            use_anti_detection=False,
        )
        crawler.request_queue = MemoryRequestQueue()

        # Mock PlaywrightCrawler._fetch_and_build_context to return a real CrawlingContext
        request = MagicMock()
        request.url = "https://example.com"
        request.headers = {}
        base_ctx = CrawlingContext(
            request=request,
            response={"body": SAMPLE_HTML, "status": 200},
            parsed=None,
            page=AsyncMock(),
            crawler=crawler,
            session=MagicMock(cookies={}),
            proxy_info=None,
            log=MagicMock(),
        )

        with patch("knowscraper.crawlers.playwright_crawler.PlaywrightCrawler._fetch_and_build_context",
                   new=AsyncMock(return_value=base_ctx)), \
             patch.object(crawler, "_setup", new=AsyncMock()), \
             patch.object(crawler, "_teardown", new=AsyncMock()):

            await crawler.run(["https://example.com"])

        assert "AICrawlingContext" in context_type_seen
