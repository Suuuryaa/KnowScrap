"""Built-in: detailed per-request logging plugin."""

from ..base_plugin import BasePlugin
from ...utils.log import get_logger
import time


class LoggingPlugin(BasePlugin):
    """
    Logs every request with timing, status, and retry info.
    Attach to any crawler for detailed request-level logs.

    Example:
        crawler = CheerioCrawler(router=router, plugins=[LoggingPlugin()])
    """

    name = "logging"

    def __init__(self, log_level: str = "INFO") -> None:
        self._log = get_logger("LoggingPlugin")
        self._start_times: dict[str, float] = {}

    async def before_request(self, request):
        self._start_times[request.unique_key] = time.time()
        self._log.info(f"→ {request.method} {request.url}" +
                       (f" [{request.label}]" if request.label else ""))
        return request

    async def after_request(self, context):
        key = context.request.unique_key
        elapsed = time.time() - self._start_times.pop(key, time.time())
        status = ""
        if context.response and isinstance(context.response, dict):
            status = f" HTTP {context.response.get('status', '?')}"
        self._log.info(f"✓ {context.request.url}{status} ({elapsed:.2f}s)")

    async def on_request_error(self, request, error):
        key = request.unique_key
        elapsed = time.time() - self._start_times.pop(key, time.time())
        self._log.error(f"✗ {request.url} — {error} ({elapsed:.2f}s)")

    async def on_request_retry(self, request, attempt):
        self._log.warning(f"↺ Retrying {request.url} (attempt {attempt})")

    async def after_crawl(self, crawler, stats):
        self._log.info(
            f"Crawl complete — {stats['requests_done']} done, "
            f"{stats['requests_failed']} failed, "
            f"{stats['requests_retried']} retried"
        )
