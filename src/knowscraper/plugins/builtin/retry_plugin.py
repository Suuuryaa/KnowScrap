"""Built-in: smart retry plugin with exponential backoff."""

from __future__ import annotations
import asyncio
from ..base_plugin import BasePlugin


class RetryPlugin(BasePlugin):
    """
    Adds exponential backoff between retries.
    Base delay doubles each attempt: 1s, 2s, 4s, 8s...

    Example:
        crawler = CheerioCrawler(
            router=router,
            plugins=[RetryPlugin(base_delay=2.0, max_delay=30.0)]
        )
    """

    name = "retry"

    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0) -> None:
        self._base_delay = base_delay
        self._max_delay = max_delay

    async def on_request_retry(self, request, attempt: int) -> None:
        delay = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
        await asyncio.sleep(delay)
