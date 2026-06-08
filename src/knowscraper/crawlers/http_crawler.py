"""
KnowScraper - HttpCrawler
Plain HTTP crawler. Uses Node.js got-scraping for real TLS fingerprinting,
falls back to httpx if Node service is unavailable.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..anti_detection.bridge import get_bridge
from ..core.configuration import Configuration
from ..core.request import Request
from ..core.router import CrawlingContext
from .base_crawler import BaseCrawler


class HttpCrawler(BaseCrawler):
    """
    Fetches pages via HTTP only — no browser.
    Fast and lightweight. Use for sites that don't require JavaScript.
    Anti-detection via got-scraping (Node.js TLS fingerprinting).
    """

    async def _setup(self) -> None:
        if self._use_anti_detection and self._config.node_service_enabled:
            bridge = get_bridge(self._config.node_service_url)
            try:
                await bridge.start()
                self._log.info("Anti-detection service started")
            except Exception as e:
                self._log.warning(f"Anti-detection service unavailable: {e}. Falling back to httpx.")
                self._use_anti_detection = False

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        proxy_url = proxy_info.url if proxy_info else None

        if self._use_anti_detection and self._config.node_service_enabled:
            response_data = await self._fetch_via_node(request, proxy_url, session)
        else:
            response_data = await self._fetch_via_httpx(request, proxy_url, session)

        return CrawlingContext(
            request=request,
            response=response_data,
            crawler=self,
            session=session,
            proxy_info=proxy_info,
            log=self._log,
        )

    async def _fetch_via_node(
        self, request: Request, proxy_url: str | None, session: Any
    ) -> dict:
        bridge = get_bridge(self._config.node_service_url)
        return await bridge.fetch(
            url=request.url,
            method=request.method,
            headers={**session.headers, **request.headers},
            payload=request.payload,
            proxy=proxy_url,
            session_token=session.id,
            timeout=self._timeout * 1000,
        )

    async def _fetch_via_httpx(
        self, request: Request, proxy_url: str | None, session: Any
    ) -> dict:
        headers = {**session.headers, **request.headers}
        proxies = {"http://": proxy_url, "https://": proxy_url} if proxy_url else None

        async with httpx.AsyncClient(proxies=proxies, timeout=self._timeout) as client:
            resp = await client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                content=request.payload if isinstance(request.payload, (str, bytes)) else None,
            )

            # Retire session on block signals
            self.session_pool.mark_session_blocked(session, resp.status_code)

            return {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text,
                "url": str(resp.url),
            }

    async def _teardown(self) -> None:
        if self._use_anti_detection:
            bridge = get_bridge(self._config.node_service_url)
            await bridge.stop()
        await super()._teardown()
