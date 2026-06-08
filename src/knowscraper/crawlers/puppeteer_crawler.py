"""
KnowScraper - PuppeteerCrawler
Browser automation via Puppeteer (Node.js) controlled from Python.
Uses the Node.js anti-detection microservice to run Puppeteer.

Use when:
- You need Puppeteer-specific behaviour
- You want Chrome DevTools Protocol access via Node.js
- Compatibility with Puppeteer-specific scripts

For most cases, PlaywrightCrawler is preferred.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from ..anti_detection.bridge import get_bridge
from ..core.request import Request
from ..core.router import CrawlingContext
from .base_crawler import BaseCrawler


class PuppeteerPage:
    """
    Thin wrapper that mimics a Playwright-like page interface
    but backed by Puppeteer via the Node.js service.
    Exposes the raw HTML and convenience methods.
    """

    def __init__(self, data: dict, crawler: "PuppeteerCrawler") -> None:
        self._data = data
        self._crawler = crawler
        self.url = data.get("url", "")
        self.cookies = data.get("cookies", [])
        self._html = data.get("html", "")
        self._soup: BeautifulSoup | None = None

    @property
    def soup(self) -> BeautifulSoup:
        if self._soup is None:
            self._soup = BeautifulSoup(self._html, "lxml")
        return self._soup

    async def content(self) -> str:
        return self._html

    async def title(self) -> str:
        return self._data.get("title", "")

    async def query_selector(self, selector: str) -> Any | None:
        el = self.soup.select_one(selector)
        return _BSElement(el) if el else None

    async def query_selector_all(self, selector: str) -> list:
        return [_BSElement(el) for el in self.soup.select(selector)]

    def screenshot_base64(self) -> str | None:
        return self._data.get("screenshot")

    def __repr__(self) -> str:
        return f"PuppeteerPage(url={self.url!r})"


class _BSElement:
    """Wraps a BeautifulSoup Tag to mimic basic Playwright ElementHandle API."""

    def __init__(self, tag) -> None:
        self._tag = tag

    async def inner_text(self) -> str:
        return self._tag.get_text(strip=True) if self._tag else ""

    async def get_attribute(self, name: str) -> str | None:
        return self._tag.get(name) if self._tag else None

    async def is_visible(self) -> bool:
        return self._tag is not None


class PuppeteerCrawler(BaseCrawler):
    """
    Crawler powered by Puppeteer (Node.js) controlled via the anti-detection microservice.

    Provides context.page — a PuppeteerPage with:
        - page.soup          → BeautifulSoup parsed document
        - page.content()     → raw HTML
        - page.title()       → page title
        - page.cookies       → list of cookies
        - page.query_selector(css)
        - page.query_selector_all(css)

    Supports custom actions (click, type, scroll, wait) before returning the page.
    """

    def __init__(
        self,
        *,
        wait_until: str = "networkidle2",
        headless: bool = True,
        screenshot: bool = False,
        pre_actions: list[dict] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._wait_until = wait_until
        self._headless = headless
        self._screenshot = screenshot
        self._pre_actions = pre_actions or []

    async def _setup(self) -> None:
        bridge = get_bridge(self._config.node_service_url)
        try:
            await bridge.start()
            self._log.info("Anti-detection service started (Puppeteer mode)")
        except Exception as e:
            self._log.warning(f"Anti-detection service unavailable: {e}")
            self._use_anti_detection = False

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        bridge = get_bridge(self._config.node_service_url)

        # Build cookies list from session
        session_cookies = [
            {"name": k, "value": v, "url": request.url}
            for k, v in session.cookies.items()
        ]

        body = {
            "url": request.url,
            "waitUntil": self._wait_until,
            "timeout": self._timeout * 1000,
            "headless": self._headless,
            "screenshot": self._screenshot,
            "actions": self._pre_actions,
            "cookies": session_cookies,
        }
        if proxy_info:
            body["proxy"] = proxy_info.url

        import httpx
        async with httpx.AsyncClient(timeout=self._timeout + 10) as client:
            resp = await client.post(
                f"{self._config.node_service_url}/puppeteer/fetch",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        # Update session cookies
        for cookie in data.get("cookies", []):
            session.cookies[cookie["name"]] = cookie["value"]

        page = PuppeteerPage(data, crawler=self)
        soup = page.soup

        return CrawlingContext(
            request=request,
            response={"status": 200, "body": data.get("html", ""), "url": data.get("url")},
            parsed=soup,
            page=page,
            crawler=self,
            session=session,
            proxy_info=proxy_info,
            log=self._log,
        )

    async def _teardown(self) -> None:
        bridge = get_bridge(self._config.node_service_url)
        await bridge.stop()
        await super()._teardown()
