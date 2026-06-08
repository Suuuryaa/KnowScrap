"""
KnowScraper - Router
Label-based request handler routing.
Assign labels to requests, define handlers per label.
"""

from __future__ import annotations

from typing import Any, Callable, Awaitable

from .request import Request


HandlerFn = Callable[["CrawlingContext"], Awaitable[None]]


class Router:
    def __init__(self) -> None:
        self._routes: dict[str | None, HandlerFn] = {}
        self._default: HandlerFn | None = None

    def default_handler(self, fn: HandlerFn) -> HandlerFn:
        """Decorator — registers the default handler (no label match needed)."""
        self._default = fn
        return fn

    def handler(self, label: str) -> Callable[[HandlerFn], HandlerFn]:
        """Decorator — registers a handler for a specific label."""
        def decorator(fn: HandlerFn) -> HandlerFn:
            self._routes[label] = fn
            return fn
        return decorator

    async def dispatch(self, context: "CrawlingContext") -> None:
        label = context.request.label
        fn = self._routes.get(label) or self._default
        if fn is None:
            raise ValueError(
                f"No handler for label={label!r} and no default handler registered."
            )
        await fn(context)


class CrawlingContext:
    """
    Passed to every handler. Contains everything needed to work with a request.
    Modelled after Crawlee's CrawlingContext.
    """

    def __init__(
        self,
        *,
        request: Request,
        response: Any = None,
        parsed: Any = None,
        page: Any = None,
        crawler: Any = None,
        session: Any = None,
        proxy_info: dict | None = None,
        log: Any = None,
    ) -> None:
        self.request = request
        self.response = response      # raw HTTP response (httpx Response or similar)
        self.parsed = parsed          # BeautifulSoup / lxml parsed doc
        self.page = page              # Playwright Page (browser crawlers only)
        self.crawler = crawler        # reference back to the crawler
        self.session = session
        self.proxy_info = proxy_info
        self.log = log

    async def enqueue_links(
        self,
        *,
        selector: str = "a[href]",
        label: str | None = None,
        base_url: str | None = None,
        patterns: list[str] | None = None,
    ) -> int:
        """
        Extract links from the current page and add them to the queue.
        Works for both HTTP (parsed) and browser (page) crawlers.
        """
        from ..utils.url_utils import extract_links, normalize_url

        base = base_url or self.request.url

        if self.page is not None:
            # browser context — extract via Playwright
            hrefs = await self.page.eval_on_selector_all(
                selector, "els => els.map(e => e.href)"
            )
        elif self.parsed is not None:
            # HTTP context — extract via BeautifulSoup
            hrefs = extract_links(self.parsed, selector=selector, base_url=base)
        else:
            return 0

        from .request import Request as Req
        requests = []
        for href in hrefs:
            url = normalize_url(href, base)
            if not url:
                continue
            if patterns and not any(p in url for p in patterns):
                continue
            requests.append(Req(url=url, label=label))

        return await self.crawler.request_queue.add_requests(requests)

    def __repr__(self) -> str:
        return f"CrawlingContext(url={self.request.url!r}, label={self.request.label!r})"
