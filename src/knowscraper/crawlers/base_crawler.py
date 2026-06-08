"""
KnowScraper - BaseCrawler
Abstract base class for all crawlers.
Handles the run loop, retries, sessions, proxies, delays, autoscaling,
robots.txt enforcement, and per-domain rate limiting.
"""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Callable, Awaitable
from urllib.parse import urlparse

from ..core.autoscaled_pool import AutoscaledPool
from ..core.configuration import Configuration
from ..core.dataset import Dataset
from ..core.proxy_configuration import ProxyConfiguration
from ..core.request import Request, RequestState
from ..core.request_queue import RequestQueue
from ..core.router import CrawlingContext, Router
from ..core.session_pool import SessionPool
from ..plugins.base_plugin import BasePlugin
from ..plugins.plugin_manager import PluginManager
from ..utils.log import get_logger
from ..utils.robots import can_fetch, get_crawl_delay


class BaseCrawler(ABC):
    def __init__(
        self,
        *,
        request_handler: Callable[[CrawlingContext], Awaitable[None]] | None = None,
        router: Router | None = None,
        max_request_retries: int | None = None,
        max_concurrency: int | None = None,
        min_concurrency: int | None = None,
        request_timeout: int | None = None,
        min_delay: float | None = None,
        max_delay: float | None = None,
        # robots.txt
        respect_robots_txt: bool = False,
        user_agent: str = "KnowScraperBot",
        # per-domain rate limiting
        max_requests_per_minute: int | None = None,
        # anti-detection
        proxy_configuration: ProxyConfiguration | None = None,
        session_pool: SessionPool | None = None,
        dataset: Dataset | None = None,
        configuration: Configuration | None = None,
        use_anti_detection: bool = True,
        plugins: list[BasePlugin] | None = None,
    ) -> None:
        self._config = configuration or Configuration.get_global()

        if router and request_handler:
            raise ValueError("Provide either router or request_handler, not both.")
        self._router = router
        self._request_handler = request_handler

        self._max_retries = max_request_retries if max_request_retries is not None else self._config.max_request_retries
        self._max_concurrency = max_concurrency or self._config.max_concurrency
        self._min_concurrency = min_concurrency or self._config.min_concurrency
        self._timeout = request_timeout or self._config.request_timeout
        self._min_delay = min_delay if min_delay is not None else self._config.min_delay
        self._max_delay = max_delay if max_delay is not None else self._config.max_delay

        self._respect_robots = respect_robots_txt
        self._user_agent = user_agent
        self._max_rpm = max_requests_per_minute

        # Per-domain rate limiting state
        self._domain_request_times: dict[str, list[float]] = defaultdict(list)
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        self.proxy_configuration = proxy_configuration
        self.session_pool = session_pool or SessionPool(max_pool_size=self._config.max_pool_size)
        self.dataset = dataset or Dataset()
        self.request_queue = RequestQueue(db_path=f"{self._config.storage_dir}/queue.db")
        self._use_anti_detection = use_anti_detection
        self._plugins = PluginManager(plugins)
        self._log = get_logger(self.__class__.__name__)

        self._pool = AutoscaledPool(
            min_concurrency=self._min_concurrency,
            max_concurrency=self._max_concurrency,
        )

        self._stats = {
            "requests_total": 0,
            "requests_done": 0,
            "requests_failed": 0,
            "requests_retried": 0,
            "requests_skipped_robots": 0,
            "start_time": 0.0,
            "end_time": 0.0,
        }

    # ── Public API ────────────────────────────────────────────────────────────

    async def add_requests(self, urls: list[str | Request], **kwargs) -> int:
        requests = []
        for item in urls:
            if isinstance(item, str):
                requests.append(Request(url=item, **kwargs))
            else:
                requests.append(item)
        return await self.request_queue.add_requests(requests)

    async def run(self, urls: list[str | Request] | None = None, resume: bool = False) -> dict:
        """
        Start the crawl. Seed with initial URLs/Requests.
        resume=True skips purging — continues an interrupted crawl.
        """
        if urls and not resume:
            await self.request_queue.purge()
            await self.dataset.drop()

        if urls:
            await self.add_requests(urls)

        await self._setup()
        await self._plugins.before_crawl(self)
        self._stats["start_time"] = time.time()
        self._log.info(f"Starting {self.__class__.__name__}")

        await self._pool.run(
            task_fn=self._process_request,
            source=self._request_source(),
        )

        self._stats["end_time"] = time.time()
        elapsed = self._stats["end_time"] - self._stats["start_time"]
        self._log.info(
            f"Finished — {self._stats['requests_done']} done, "
            f"{self._stats['requests_failed']} failed, "
            f"{self._stats['requests_skipped_robots']} skipped (robots.txt) "
            f"in {elapsed:.1f}s"
        )

        await self._plugins.after_crawl(self, self._stats)
        await self._teardown()
        return self._stats

    # ── Internal run loop ─────────────────────────────────────────────────────

    async def _request_source(self):
        while True:
            req = await self.request_queue.fetch_next()
            if req is None:
                await asyncio.sleep(0.2)
                if await self.request_queue.is_empty():
                    break
                continue
            self._stats["requests_total"] += 1
            yield req

    async def _process_request(self, request: Request) -> None:
        # robots.txt check
        if self._respect_robots:
            allowed = await can_fetch(request.url, self._user_agent)
            if not allowed:
                self._log.warning(f"Blocked by robots.txt: {request.url}")
                self._stats["requests_skipped_robots"] += 1
                await self.request_queue.mark_done(request)
                return

        # Per-domain rate limiting
        await self._enforce_rate_limit(request.url)

        # Configurable delay
        if self._min_delay or self._max_delay:
            delay = random.uniform(self._min_delay, self._max_delay)
            if delay > 0:
                await asyncio.sleep(delay)

        # Session + proxy
        proxy_info = self.proxy_configuration.new_proxy_info() if self.proxy_configuration else None
        session = await self.session_pool.get_session(
            proxy=proxy_info.url if proxy_info else None
        )

        try:
            request = await self._plugins.before_request(request)
            context = await self._fetch_and_build_context(request, session, proxy_info)
            await self._dispatch(context)
            await self._plugins.after_request(context)
            await self.request_queue.mark_done(request)
            self._stats["requests_done"] += 1

        except Exception as exc:
            self._log.error(f"Error on {request.url}: {exc}")
            self._stats["requests_failed"] += 1
            await self._plugins.on_request_error(request, exc)

            if request.can_retry:
                self._stats["requests_retried"] += 1
                await self._plugins.on_request_retry(request, request.retry_count + 1)
                await self.request_queue.mark_failed(request)
                self._log.warning(
                    f"Retrying {request.url} "
                    f"(attempt {request.retry_count}/{request.max_retries})"
                )
            else:
                await self.request_queue.mark_failed(request)
                self._log.error(
                    f"Giving up on {request.url} after {request.retry_count} retries"
                )

    async def _enforce_rate_limit(self, url: str) -> None:
        """Sliding-window per-domain rate limiter. Blocks if over max_requests_per_minute."""
        if not self._max_rpm:
            return

        domain = urlparse(url).netloc
        window = 60.0
        max_req = self._max_rpm

        async with self._domain_locks[domain]:
            now = time.time()
            # Remove timestamps older than the window
            self._domain_request_times[domain] = [
                t for t in self._domain_request_times[domain] if now - t < window
            ]

            if len(self._domain_request_times[domain]) >= max_req:
                # Wait until the oldest request falls out of the window
                oldest = self._domain_request_times[domain][0]
                sleep_for = window - (now - oldest) + 0.1
                if sleep_for > 0:
                    self._log.debug(
                        f"Rate limit: sleeping {sleep_for:.1f}s for {domain}"
                    )
                    await asyncio.sleep(sleep_for)

            self._domain_request_times[domain].append(time.time())

    async def _dispatch(self, context: CrawlingContext) -> None:
        if self._router:
            await self._router.dispatch(context)
        elif self._request_handler:
            await self._request_handler(context)
        else:
            raise RuntimeError("No handler or router configured.")

    @abstractmethod
    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        ...

    async def _setup(self) -> None:
        pass

    async def _teardown(self) -> None:
        self.request_queue.close()

    async def push_data(self, data: dict | list[dict]) -> None:
        """Push data through plugin on_data hooks then to dataset."""
        records = data if isinstance(data, list) else [data]
        filtered = []
        for record in records:
            result = await self._plugins.on_data(record)
            if result is not None:
                filtered.append(result)
        if filtered:
            await self.dataset.push_data(filtered if len(filtered) > 1 else filtered[0])

    @property
    def stats(self) -> dict:
        return self._stats.copy()
