"""
KnowScraper - CheerioCrawler
HTTP crawler with automatic HTML parsing via BeautifulSoup.
Equivalent to Crawlee's CheerioCrawler — fast, no browser needed.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from ..core.request import Request
from ..core.router import CrawlingContext
from .http_crawler import HttpCrawler


class CheerioCrawler(HttpCrawler):
    """
    Fetches pages via HTTP and parses HTML with BeautifulSoup (like Cheerio).
    context.parsed gives you a BeautifulSoup object.
    context.response gives you the raw response dict.

    Best for: static HTML sites, blogs, news sites, e-commerce (without JS rendering).
    """

    def __init__(self, *, parser: str = "lxml", **kwargs) -> None:
        super().__init__(**kwargs)
        self._parser = parser  # "lxml", "html.parser", "html5lib"

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        # Get raw HTTP response from parent
        context = await super()._fetch_and_build_context(request, session, proxy_info)

        # Parse HTML
        body = context.response.get("body", "") if isinstance(context.response, dict) else ""
        soup = BeautifulSoup(body, self._parser)

        return CrawlingContext(
            request=request,
            response=context.response,
            parsed=soup,
            crawler=self,
            session=session,
            proxy_info=proxy_info,
            log=self._log,
        )
