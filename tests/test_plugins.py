"""Tests for the plugin system and built-in plugins."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from knowscraper.plugins import BasePlugin, PluginManager
from knowscraper.plugins.builtin import DedupPlugin, RetryPlugin, StatsPlugin, LoggingPlugin
from knowscraper.core.request import Request


# ── PluginManager ─────────────────────────────────────────────────────────────

class TestPluginManager:
    async def test_empty_manager(self):
        pm = PluginManager()
        req = Request(url="https://example.com")
        result = await pm.before_request(req)
        assert result is req

    async def test_before_request_passes_through(self):
        class TagPlugin(BasePlugin):
            name = "tag"
            async def before_request(self, request):
                request.label = "tagged"
                return request

        pm = PluginManager([TagPlugin()])
        req = Request(url="https://example.com")
        req = await pm.before_request(req)
        assert req.label == "tagged"

    async def test_on_data_drop(self):
        class DropAll(BasePlugin):
            name = "drop"
            async def on_data(self, data):
                return None

        pm = PluginManager([DropAll()])
        assert await pm.on_data({"x": 1}) is None

    async def test_on_data_transform(self):
        class AddField(BasePlugin):
            name = "add"
            async def on_data(self, data):
                data["extra"] = True
                return data

        pm = PluginManager([AddField()])
        result = await pm.on_data({"x": 1})
        assert result == {"x": 1, "extra": True}

    async def test_multiple_plugins_chain(self):
        results = []

        class A(BasePlugin):
            name = "a"
            async def on_data(self, data):
                results.append("a")
                return data

        class B(BasePlugin):
            name = "b"
            async def on_data(self, data):
                results.append("b")
                return data

        pm = PluginManager([A(), B()])
        await pm.on_data({})
        assert results == ["a", "b"]

    def test_repr(self):
        pm = PluginManager([DedupPlugin()])
        assert "dedup" in repr(pm)


# ── DedupPlugin ───────────────────────────────────────────────────────────────

class TestDedupPlugin:
    async def test_passes_unique(self):
        plugin = DedupPlugin()
        result = await plugin.on_data({"url": "https://a.com"})
        assert result == {"url": "https://a.com"}

    async def test_drops_duplicate(self):
        plugin = DedupPlugin()
        await plugin.on_data({"url": "https://a.com"})
        result = await plugin.on_data({"url": "https://a.com"})
        assert result is None

    async def test_dedup_by_key(self):
        plugin = DedupPlugin(key="url")
        await plugin.on_data({"url": "https://a.com", "title": "First"})
        result = await plugin.on_data({"url": "https://a.com", "title": "Different"})
        assert result is None

    async def test_different_keys_pass(self):
        plugin = DedupPlugin(key="url")
        await plugin.on_data({"url": "https://a.com"})
        result = await plugin.on_data({"url": "https://b.com"})
        assert result is not None

    async def test_stats(self):
        plugin = DedupPlugin()
        await plugin.on_data({"x": 1})
        await plugin.on_data({"x": 1})
        assert plugin.stats["unique"] == 1
        assert plugin.stats["dropped"] == 1


# ── RetryPlugin ───────────────────────────────────────────────────────────────

class TestRetryPlugin:
    async def test_delay_increases_exponentially(self):
        delays = []
        import asyncio

        original_sleep = asyncio.sleep

        async def fake_sleep(t):
            delays.append(t)

        plugin = RetryPlugin(base_delay=1.0, max_delay=30.0)
        req = Request(url="https://example.com")

        import unittest.mock as mock
        with mock.patch("asyncio.sleep", side_effect=fake_sleep):
            await plugin.on_request_retry(req, 1)
            await plugin.on_request_retry(req, 2)
            await plugin.on_request_retry(req, 3)

        assert delays == [1.0, 2.0, 4.0]

    async def test_max_delay_cap(self):
        delays = []

        async def fake_sleep(t):
            delays.append(t)

        plugin = RetryPlugin(base_delay=10.0, max_delay=15.0)
        req = Request(url="https://example.com")

        import unittest.mock as mock
        with mock.patch("asyncio.sleep", side_effect=fake_sleep):
            await plugin.on_request_retry(req, 3)  # would be 40s without cap

        assert delays[0] == 15.0


# ── StatsPlugin ───────────────────────────────────────────────────────────────

class TestStatsPlugin:
    def _make_request(self, url, label=None):
        req = Request(url=url, label=label)
        req.unique_key = req.unique_key  # ensure set
        return req

    def _make_context(self, request):
        ctx = MagicMock()
        ctx.request = request
        return ctx

    async def test_before_request_increments_domain(self):
        plugin = StatsPlugin()
        req = self._make_request("https://example.com/page")
        await plugin.before_request(req)
        assert plugin.report()["requests_by_domain"]["example.com"] == 1

    async def test_label_tracking(self):
        plugin = StatsPlugin()
        req = self._make_request("https://example.com", label="listing")
        await plugin.before_request(req)
        assert plugin.report()["requests_by_label"]["listing"] == 1

    async def test_response_time(self):
        import time
        plugin = StatsPlugin()
        req = self._make_request("https://example.com")
        await plugin.before_request(req)
        time.sleep(0.01)
        ctx = self._make_context(req)
        await plugin.after_request(ctx)
        report = plugin.report()
        assert report["avg_response_time"] > 0

    async def test_error_tracking(self):
        plugin = StatsPlugin()
        req = self._make_request("https://example.com")
        await plugin.on_request_error(req, Exception("fail"))
        assert plugin.report()["errors_by_domain"]["example.com"] == 1

    async def test_data_count(self):
        plugin = StatsPlugin()
        await plugin.on_data({"x": 1})
        await plugin.on_data({"x": 2})
        assert plugin.report()["data_records_saved"] == 2

    async def test_empty_report(self):
        plugin = StatsPlugin()
        report = plugin.report()
        assert report["avg_response_time"] == 0
        assert report["data_records_saved"] == 0
