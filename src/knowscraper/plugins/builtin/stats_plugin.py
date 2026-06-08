"""Built-in: live stats tracking plugin."""

from __future__ import annotations
import time
from collections import defaultdict
from ..base_plugin import BasePlugin


class StatsPlugin(BasePlugin):
    """
    Tracks per-domain stats, response times, and error rates.
    Access stats during or after crawl.

    Example:
        stats_plugin = StatsPlugin()
        crawler = CheerioCrawler(router=router, plugins=[stats_plugin])
        await crawler.run(["https://example.com"])
        print(stats_plugin.report())
    """

    name = "stats"

    def __init__(self) -> None:
        self._domain_counts: dict[str, int] = defaultdict(int)
        self._domain_errors: dict[str, int] = defaultdict(int)
        self._response_times: list[float] = []
        self._start_times: dict[str, float] = {}
        self._label_counts: dict[str, int] = defaultdict(int)
        self._total_data_pushed = 0

    async def before_request(self, request):
        from urllib.parse import urlparse
        self._start_times[request.unique_key] = time.time()
        domain = urlparse(request.url).netloc
        self._domain_counts[domain] += 1
        if request.label:
            self._label_counts[request.label] += 1
        return request

    async def after_request(self, context):
        key = context.request.unique_key
        if key in self._start_times:
            elapsed = time.time() - self._start_times.pop(key)
            self._response_times.append(elapsed)

    async def on_request_error(self, request, error):
        from urllib.parse import urlparse
        domain = urlparse(request.url).netloc
        self._domain_errors[domain] += 1
        self._start_times.pop(request.unique_key, None)

    async def on_data(self, data):
        self._total_data_pushed += 1
        return data

    def report(self) -> dict:
        times = self._response_times
        return {
            "requests_by_domain": dict(self._domain_counts),
            "errors_by_domain":   dict(self._domain_errors),
            "requests_by_label":  dict(self._label_counts),
            "data_records_saved": self._total_data_pushed,
            "avg_response_time":  round(sum(times) / len(times), 3) if times else 0,
            "min_response_time":  round(min(times), 3) if times else 0,
            "max_response_time":  round(max(times), 3) if times else 0,
        }
