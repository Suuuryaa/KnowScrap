"""KnowScraper - PluginManager — runs all registered plugins for each hook."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .base_plugin import BasePlugin

if TYPE_CHECKING:
    from ..core.request import Request
    from ..core.router import CrawlingContext


class PluginManager:
    def __init__(self, plugins: list[BasePlugin] | None = None) -> None:
        self._plugins: list[BasePlugin] = plugins or []

    def register(self, plugin: BasePlugin) -> None:
        self._plugins.append(plugin)

    async def before_crawl(self, crawler: Any) -> None:
        for p in self._plugins:
            await p.before_crawl(crawler)

    async def after_crawl(self, crawler: Any, stats: dict) -> None:
        for p in self._plugins:
            await p.after_crawl(crawler, stats)

    async def before_request(self, request: "Request") -> "Request":
        for p in self._plugins:
            request = await p.before_request(request)
        return request

    async def after_request(self, context: "CrawlingContext") -> None:
        for p in self._plugins:
            await p.after_request(context)

    async def on_request_error(self, request: "Request", error: Exception) -> None:
        for p in self._plugins:
            await p.on_request_error(request, error)

    async def on_request_retry(self, request: "Request", attempt: int) -> None:
        for p in self._plugins:
            await p.on_request_retry(request, attempt)

    async def before_enqueue(self, urls: list[str]) -> list[str]:
        for p in self._plugins:
            urls = await p.before_enqueue(urls)
        return urls

    async def on_data(self, data: dict) -> dict | None:
        for p in self._plugins:
            result = await p.on_data(data)
            if result is None:
                return None  # plugin dropped the record
            data = result
        return data

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        names = [p.name for p in self._plugins]
        return f"PluginManager(plugins={names})"
