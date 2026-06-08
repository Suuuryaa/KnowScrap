"""
KnowScraper - Plugin Ecosystem
Hook-based plugin architecture.
Plugins can intercept any stage of the crawl lifecycle.
"""

from .base_plugin import BasePlugin, PluginHooks
from .plugin_manager import PluginManager
from .builtin.retry_plugin import RetryPlugin
from .builtin.logging_plugin import LoggingPlugin
from .builtin.dedup_plugin import DedupPlugin
from .builtin.stats_plugin import StatsPlugin

__all__ = [
    "BasePlugin",
    "PluginHooks",
    "PluginManager",
    "RetryPlugin",
    "LoggingPlugin",
    "DedupPlugin",
    "StatsPlugin",
]
