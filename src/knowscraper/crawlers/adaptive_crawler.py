"""
KnowScraper - AdaptiveCrawler
Automatically detects whether a page needs a real browser or plain HTTP.
Tries HTTP first — if JS rendering is detected, upgrades to browser.
Mirrors Crawlee's AdaptivePlaywrightCrawler.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..core.request import Request
from ..core.router import CrawlingContext
from .cheerio_crawler import CheerioCrawler
from .playwright_crawler import PlaywrightCrawler


# Signals that a page needs JS rendering
JS_FRAMEWORK_PATTERNS = [
    r'<div id=["\']root["\']>\s*</div>',   # React
    r'<div id=["\']app["\']>\s*</div>',    # Vue
    r'ng-version=',                         # Angular
    r'__NEXT_DATA__',                       # Next.js
    r'__NUXT__',                            # Nuxt.js
    r'window\.__INITIAL_STATE__',
    r'data-reactroot',
]

JS_PATTERN = re.compile("|".join(JS_FRAMEWORK_PATTERNS), re.IGNORECASE)


class AdaptiveCrawler(CheerioCrawler):
    """
    Smart crawler that starts with HTTP and upgrades to browser when needed.

    Saves resources by avoiding the browser for pages that don't need it.
    Automatically upgrades to Playwright when it detects:
    - Empty HTML body (JS-rendered content)
    - React/Vue/Angular/Next.js framework signatures
    - Missing expected content after HTTP fetch
    """

    def __init__(self, *, content_selector: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        # Optional CSS selector — if not found after HTTP fetch, upgrade to browser
        self._content_selector = content_selector
        self._playwright_crawler: PlaywrightCrawler | None = None

    async def _setup(self) -> None:
        await super()._setup()
        # Pre-initialize playwright crawler (lazy browser launch)
        self._playwright_crawler = PlaywrightCrawler(
            browser_type=self._config.browser_type,
            headless=self._config.headless,
            configuration=self._config,
            use_anti_detection=self._use_anti_detection,
            session_pool=self.session_pool,
            proxy_configuration=self.proxy_configuration,
            dataset=self.dataset,
        )
        # Share the same queue so enqueued links go to one place
        self._playwright_crawler.request_queue = self.request_queue

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        # Try HTTP first
        context = await super()._fetch_and_build_context(request, session, proxy_info)

        if self._needs_browser(context):
            self._log.debug(f"Upgrading to browser for {request.url}")
            await self._ensure_browser_started()
            return await self._playwright_crawler._fetch_and_build_context(
                request, session, proxy_info
            )

        return context

    def _needs_browser(self, context: CrawlingContext) -> bool:
        body = context.response.get("body", "") if isinstance(context.response, dict) else ""

        # Check for JS framework signatures
        if JS_PATTERN.search(body):
            return True

        # Check if body is nearly empty
        soup: BeautifulSoup = context.parsed
        if soup:
            text = soup.get_text(strip=True)
            if len(text) < 200 and len(body) > 500:
                return True

        # Check if required selector is missing
        if self._content_selector and soup:
            if not soup.select_one(self._content_selector):
                return True

        return False

    async def _ensure_browser_started(self) -> None:
        if self._playwright_crawler and self._playwright_crawler._browser is None:
            await self._playwright_crawler._setup()

    async def _teardown(self) -> None:
        if self._playwright_crawler:
            await self._playwright_crawler._teardown()
        await super()._teardown()
