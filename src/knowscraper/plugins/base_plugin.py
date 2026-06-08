"""
KnowScraper - BasePlugin
Abstract base class for all plugins.
Override only the hooks you need.
"""

from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.request import Request
    from ..core.router import CrawlingContext


class PluginHooks(str, Enum):
    BEFORE_CRAWL        = "before_crawl"        # crawler starts
    AFTER_CRAWL         = "after_crawl"         # crawler finishes
    BEFORE_REQUEST      = "before_request"      # before each request is fetched
    AFTER_REQUEST       = "after_request"       # after handler runs, before mark_done
    ON_REQUEST_ERROR    = "on_request_error"    # when a request fails
    ON_REQUEST_RETRY    = "on_request_retry"    # when a request is retried
    BEFORE_ENQUEUE      = "before_enqueue"      # before URLs are added to queue
    ON_DATA             = "on_data"             # when dataset.push_data is called


class BasePlugin(ABC):
    """
    Base class for KnowScraper plugins.

    Plugins are attached to a crawler and receive lifecycle hooks.
    Override the hooks you care about — all are no-ops by default.

    Example:
        class MyPlugin(BasePlugin):
            name = "my_plugin"

            async def before_request(self, request):
                print(f"About to fetch: {request.url}")

        crawler = CheerioCrawler(router=router, plugins=[MyPlugin()])
    """

    name: str = "unnamed_plugin"

    async def before_crawl(self, crawler: Any) -> None:
        """Called once when the crawl starts."""
        pass

    async def after_crawl(self, crawler: Any, stats: dict) -> None:
        """Called once when the crawl finishes. stats = final run stats."""
        pass

    async def before_request(self, request: "Request") -> "Request":
        """
        Called before each request is fetched.
        Can modify the request (e.g. add headers). Must return the request.
        """
        return request

    async def after_request(self, context: "CrawlingContext") -> None:
        """Called after the handler runs successfully."""
        pass

    async def on_request_error(self, request: "Request", error: Exception) -> None:
        """Called when a request raises an exception."""
        pass

    async def on_request_retry(self, request: "Request", attempt: int) -> None:
        """Called when a request is about to be retried."""
        pass

    async def before_enqueue(self, urls: list[str]) -> list[str]:
        """
        Called before URLs are added to the queue.
        Can filter or modify the URL list. Must return the list.
        """
        return urls

    async def on_data(self, data: dict) -> dict | None:
        """
        Called when data is pushed to the dataset.
        Can transform or filter data. Return None to drop the record.
        Must return the (possibly modified) data dict.
        """
        return data

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
