"""
KnowScraper — Knowledge Scraper Framework
A Crawlee-inspired web scraping framework.
Python core + Node.js anti-detection.
"""

from .core import (
    Request,
    RequestQueue,
    Router,
    CrawlingContext,
    Dataset,
    Configuration,
    SessionPool,
    ProxyConfiguration,
    AutoscaledPool,
)
from .crawlers import (
    BaseCrawler,
    HttpCrawler,
    CheerioCrawler,
    PlaywrightCrawler,
    AdaptiveCrawler,
    PuppeteerCrawler,
    AICrawler,
    AICrawlingContext,
)
from .anti_detection import AntiDetectionBridge, get_bridge
from .anti_detection.captcha import CaptchaHandler, CaptchaType
from .storage import LocalStorage
from .storage.memory_storage import MemoryRequestQueue, MemoryDataset, MemoryKeyValueStore
from .utils.robots import can_fetch, get_crawl_delay
from .utils.sitemap import fetch_sitemap_urls, discover_valid_sitemaps
from .platform import KnowPlatform, RunConfig
from .plugins import BasePlugin, PluginManager
from .plugins.builtin import LoggingPlugin, DedupPlugin, RetryPlugin, StatsPlugin

__version__ = "0.1.0"

__all__ = [
    # Core
    "Request",
    "RequestQueue",
    "Router",
    "CrawlingContext",
    "Dataset",
    "Configuration",
    "SessionPool",
    "ProxyConfiguration",
    "AutoscaledPool",
    # Crawlers
    "BaseCrawler",
    "HttpCrawler",
    "CheerioCrawler",
    "PlaywrightCrawler",
    "AdaptiveCrawler",
    "PuppeteerCrawler",
    "AICrawler",
    "AICrawlingContext",
    # Anti-detection
    "AntiDetectionBridge",
    "get_bridge",
    "CaptchaHandler",
    "CaptchaType",
    # Storage
    "LocalStorage",
    "MemoryRequestQueue",
    "MemoryDataset",
    "MemoryKeyValueStore",
    # Utils
    "can_fetch",
    "get_crawl_delay",
    "fetch_sitemap_urls",
    "discover_valid_sitemaps",
    # Platform
    "KnowPlatform",
    "RunConfig",
    # Plugins
    "BasePlugin",
    "PluginManager",
    "LoggingPlugin",
    "DedupPlugin",
    "RetryPlugin",
    "StatsPlugin",
]
