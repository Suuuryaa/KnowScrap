"""
Tests for PlaywrightCrawler stealth and fingerprint injection.
Mocks Playwright browser objects — no real Chromium needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from knowscraper.anti_detection.stealth import (
    apply_stealth,
    human_mouse_move,
    human_click,
    human_scroll,
    human_type,
    random_viewport_interaction,
    STEALTH_SCRIPTS,
)
from knowscraper.crawlers.playwright_crawler import PlaywrightCrawler
from knowscraper.core.router import Router
from knowscraper.storage.memory_storage import MemoryDataset, MemoryRequestQueue


# ── Stealth script content checks ────────────────────────────────────────────

class TestStealthScripts:
    def test_removes_webdriver_flag(self):
        assert "webdriver" in STEALTH_SCRIPTS
        assert "undefined" in STEALTH_SCRIPTS

    def test_overrides_plugins(self):
        assert "plugins" in STEALTH_SCRIPTS
        assert "Chrome PDF Plugin" in STEALTH_SCRIPTS

    def test_overrides_languages(self):
        assert "languages" in STEALTH_SCRIPTS
        assert "en-US" in STEALTH_SCRIPTS

    def test_hides_automation_markers(self):
        assert "chrome" in STEALTH_SCRIPTS.lower()


# ── apply_stealth ─────────────────────────────────────────────────────────────

class TestApplyStealth:
    async def test_injects_init_script(self):
        mock_page = AsyncMock()
        mock_page.add_init_script = AsyncMock()

        await apply_stealth(mock_page)

        mock_page.add_init_script.assert_called_once()
        injected = mock_page.add_init_script.call_args[0][0]
        assert "webdriver" in injected

    async def test_apply_stealth_does_not_raise(self):
        mock_page = AsyncMock()
        mock_page.add_init_script = AsyncMock()
        await apply_stealth(mock_page)  # should not raise


# ── Human-like interactions ───────────────────────────────────────────────────

class TestHumanMouseMove:
    async def test_calls_mouse_move(self):
        mock_page = AsyncMock()
        mock_page.mouse = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[0, 0])

        await human_mouse_move(mock_page, 100, 200)

        assert mock_page.mouse.move.call_count >= 1

    async def test_generates_bezier_path(self):
        """Mouse should move via multiple intermediate points, not teleport."""
        mock_page = AsyncMock()
        mock_page.mouse = AsyncMock()
        positions = []

        async def record_move(x, y, **kwargs):
            positions.append((x, y))

        mock_page.evaluate = AsyncMock(return_value=[0, 0])
        mock_page.mouse.move = record_move

        await human_mouse_move(mock_page, 500, 500)

        assert len(positions) >= 2  # should have intermediate points


class TestHumanClick:
    async def test_clicks_after_moving(self):
        mock_page = AsyncMock()
        mock_page.mouse = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.mouse.click = AsyncMock()

        el_box = {"x": 100, "y": 150, "width": 80, "height": 30}
        mock_el = AsyncMock()
        mock_el.bounding_box = AsyncMock(return_value=el_box)
        mock_page.query_selector = AsyncMock(return_value=mock_el)

        await human_click(mock_page, "button#submit")

        mock_page.mouse.click.assert_called_once()

    async def test_handles_missing_element(self):
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        # Should not raise even if element not found
        await human_click(mock_page, "#nonexistent")


class TestHumanScroll:
    async def test_scroll_down(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()

        await human_scroll(mock_page, direction="down", amount=300)

        assert mock_page.evaluate.call_count >= 1
        # Verify scrollBy was called with positive Y
        call_args = mock_page.evaluate.call_args_list
        assert any("scrollBy" in str(a) for a in call_args)

    async def test_scroll_up(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()

        await human_scroll(mock_page, direction="up", amount=200)

        assert mock_page.evaluate.call_count >= 1


class TestHumanType:
    async def test_types_each_character(self):
        mock_page = AsyncMock()
        mock_el = AsyncMock()
        mock_el.bounding_box = AsyncMock(return_value={"x": 10, "y": 10, "width": 100, "height": 30})
        mock_page.query_selector = AsyncMock(return_value=mock_el)
        mock_page.mouse = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.mouse.click = AsyncMock()
        mock_page.keyboard = AsyncMock()
        mock_page.keyboard.type = AsyncMock()
        mock_page.keyboard.press = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[0, 0])

        await human_type(mock_page, "#input", "hello")

        # keyboard.type called once per character (at minimum)
        assert mock_page.keyboard.type.call_count >= len("hello")

    async def test_handles_missing_element(self):
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.mouse = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.mouse.click = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[0, 0])

        await human_type(mock_page, "#missing", "test")  # should not raise


class TestRandomViewportInteraction:
    async def test_does_multiple_interactions(self):
        mock_page = AsyncMock()
        mock_page.mouse = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.evaluate = AsyncMock()

        await random_viewport_interaction(mock_page)

        # Should call mouse move and/or scroll at least once
        total_calls = mock_page.mouse.move.call_count + mock_page.evaluate.call_count
        assert total_calls >= 1


# ── PlaywrightCrawler with mocked browser ────────────────────────────────────

class TestPlaywrightCrawlerMocked:
    def _make_mock_browser(self):
        """Build a fake Playwright browser hierarchy."""
        mock_page = AsyncMock()
        mock_page.add_init_script = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>hello</body></html>")
        mock_page.title = AsyncMock(return_value="Hello")

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.add_cookies = AsyncMock()
        mock_context.set_extra_http_headers = AsyncMock()
        mock_context.add_init_script = AsyncMock()
        mock_context.cookies = AsyncMock(return_value=[])
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_obj = AsyncMock()
        mock_playwright_obj.chromium = mock_chromium
        mock_playwright_obj.stop = AsyncMock()

        return mock_playwright_obj, mock_browser, mock_context, mock_page

    async def test_stealth_applied_before_navigation(self):
        router = Router()
        dataset = MemoryDataset()
        stealth_called = []

        @router.default_handler
        async def handler(ctx):
            pass

        crawler = PlaywrightCrawler(
            router=router,
            dataset=dataset,
            stealth_mode=True,
            inject_fingerprint=False,
            use_anti_detection=False,
        )
        crawler.request_queue = MemoryRequestQueue()

        mock_pw, mock_browser, mock_ctx, mock_page = self._make_mock_browser()

        async def fake_apply_stealth(page):
            stealth_called.append(page)

        with patch("knowscraper.crawlers.playwright_crawler.apply_stealth", side_effect=fake_apply_stealth):
            # Bypass _setup — inject mocked browser directly
            crawler._playwright = mock_pw
            crawler._browser = mock_browser
            crawler._use_anti_detection = False

            req = MagicMock()
            req.url = "https://example.com"
            req.headers = {}
            session = MagicMock(cookies={})
            proxy_info = None

            ctx = await crawler._fetch_and_build_context(req, session, proxy_info)

        assert len(stealth_called) == 1
        assert ctx.page is mock_page

    async def test_fingerprint_inject_scripts_called(self):
        crawler = PlaywrightCrawler(
            router=Router(),
            dataset=MemoryDataset(),

            inject_fingerprint=True,
            use_anti_detection=False,
        )

        mock_context = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        fingerprint_data = {
            "fingerprint": {
                "navigator": {"platform": "Win32", "hardwareConcurrency": 8, "deviceMemory": 8},
                "videoCard": {"renderer": "ANGLE (Intel)", "vendor": "Google Inc."},
                "screen": {"width": 1920, "height": 1080},
            },
            "headers": {"user-agent": "Mozilla/5.0"},
        }

        await crawler._inject_fingerprint_scripts(mock_context, fingerprint_data)

        assert mock_context.add_init_script.call_count >= 1
        all_scripts = " ".join(
            str(c.args[0]) for c in mock_context.add_init_script.call_args_list
        )
        assert "Win32" in all_scripts
        assert "ANGLE" in all_scripts

    async def test_no_stealth_when_disabled(self):
        router = Router()
        stealth_calls = []

        @router.default_handler
        async def handler(ctx):
            pass

        crawler = PlaywrightCrawler(
            router=Router(),
            dataset=MemoryDataset(),

            stealth_mode=False,
            inject_fingerprint=False,
            use_anti_detection=False,
        )

        _, mock_browser, mock_ctx, mock_page = self._make_mock_browser()

        crawler._playwright = MagicMock()
        crawler._browser = mock_browser
        crawler._use_anti_detection = False

        req = MagicMock()
        req.url = "https://example.com"
        req.headers = {}
        session = MagicMock(cookies={})

        with patch("knowscraper.crawlers.playwright_crawler.apply_stealth",
                   side_effect=lambda p: stealth_calls.append(p)):
            await crawler._fetch_and_build_context(req, session, None)

        assert len(stealth_calls) == 0

    async def test_random_interactions_triggered(self):
        interaction_calls = []

        async def fake_interactions(page):
            interaction_calls.append(page)

        crawler = PlaywrightCrawler(
            router=Router(),
            dataset=MemoryDataset(),

            random_interactions=True,
            stealth_mode=False,
            inject_fingerprint=False,
            use_anti_detection=False,
        )

        _, mock_browser, mock_ctx, mock_page = self._make_mock_browser()
        crawler._playwright = MagicMock()
        crawler._browser = mock_browser
        crawler._use_anti_detection = False

        req = MagicMock()
        req.url = "https://example.com"
        req.headers = {}
        session = MagicMock(cookies={})

        with patch("knowscraper.crawlers.playwright_crawler.random_viewport_interaction",
                   side_effect=fake_interactions):
            await crawler._fetch_and_build_context(req, session, None)

        assert len(interaction_calls) == 1
