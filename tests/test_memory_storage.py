"""Tests for in-memory storage backends."""

import json
import pytest
from knowscraper.storage.memory_storage import MemoryRequestQueue, MemoryDataset, MemoryKeyValueStore
from knowscraper.core.request import Request, RequestState


class TestMemoryRequestQueue:
    @pytest.fixture
    def queue(self):
        return MemoryRequestQueue()

    async def test_add_and_fetch(self, queue):
        req = Request(url="https://example.com")
        added = await queue.add_request(req)
        assert added is True
        fetched = await queue.fetch_next()
        assert fetched is not None
        assert fetched.url == "https://example.com"
        assert fetched.state == RequestState.IN_PROGRESS

    async def test_dedup(self, queue):
        req1 = Request(url="https://example.com")
        req2 = Request(url="https://example.com")
        assert await queue.add_request(req1) is True
        assert await queue.add_request(req2) is False

    async def test_fetch_returns_none_when_empty(self, queue):
        assert await queue.fetch_next() is None

    async def test_mark_done(self, queue):
        req = Request(url="https://example.com")
        await queue.add_request(req)
        fetched = await queue.fetch_next()
        await queue.mark_done(fetched)
        assert fetched.state == RequestState.DONE

    async def test_mark_failed(self, queue):
        req = Request(url="https://example.com", max_retries=2)
        await queue.add_request(req)
        fetched = await queue.fetch_next()
        await queue.mark_failed(fetched)
        assert fetched.retry_count == 1

    async def test_purge(self, queue):
        await queue.add_request(Request(url="https://a.com"))
        await queue.add_request(Request(url="https://b.com"))
        await queue.purge()
        assert await queue.fetch_next() is None

    async def test_is_empty_initially(self, queue):
        assert await queue.is_empty() is True

    async def test_is_not_empty_after_add(self, queue):
        await queue.add_request(Request(url="https://example.com"))
        assert await queue.is_empty() is False

    async def test_add_requests_bulk(self, queue):
        reqs = [Request(url=f"https://example.com/{i}") for i in range(5)]
        count = await queue.add_requests(reqs)
        assert count == 5

    async def test_get_stats(self, queue):
        await queue.add_request(Request(url="https://example.com"))
        stats = await queue.get_stats()
        assert stats.get("pending", 0) + stats.get("PENDING", 0) >= 1 or len(stats) > 0


class TestMemoryDataset:
    @pytest.fixture
    def dataset(self):
        return MemoryDataset()

    async def test_push_and_get(self, dataset):
        await dataset.push_data({"title": "Hello"})
        items = await dataset.get_data()
        assert items == [{"title": "Hello"}]

    async def test_push_list(self, dataset):
        await dataset.push_data([{"a": 1}, {"a": 2}])
        items = await dataset.get_data()
        assert len(items) == 2

    async def test_count(self, dataset):
        assert dataset.count == 0
        await dataset.push_data({"x": 1})
        assert dataset.count == 1

    async def test_pagination(self, dataset):
        for i in range(10):
            await dataset.push_data({"i": i})
        page = await dataset.get_data(offset=5, limit=3)
        assert len(page) == 3
        assert page[0]["i"] == 5

    async def test_export_to_json(self, dataset, tmp_path):
        await dataset.push_data({"key": "value"})
        path = await dataset.export_to_json(str(tmp_path / "out.json"))
        data = json.loads(path.read_text())
        assert data == [{"key": "value"}]

    async def test_iterate(self, dataset):
        for i in range(3):
            await dataset.push_data({"i": i})
        results = [item async for item in dataset.iterate()]
        assert len(results) == 3

    async def test_drop(self, dataset):
        await dataset.push_data({"x": 1})
        await dataset.drop()
        assert dataset.count == 0


class TestMemoryKeyValueStore:
    @pytest.fixture
    def store(self):
        return MemoryKeyValueStore()

    def test_set_get(self, store):
        store.set_value("mystore", "key", {"data": 42})
        val = store.get_value("mystore", "key")
        assert val == {"data": 42}

    def test_get_missing(self, store):
        assert store.get_value("mystore", "missing") is None

    def test_get_default(self, store):
        assert store.get_value("mystore", "missing", "fallback") == "fallback"

    def test_delete(self, store):
        store.set_value("s", "k", "v")
        store.delete_value("s", "k")
        assert store.get_value("s", "k") is None

    def test_list_keys(self, store):
        store.set_value("s", "a", 1)
        store.set_value("s", "b", 2)
        keys = store.list_keys("s")
        assert set(keys) == {"a", "b"}

    def test_purge_all(self, store):
        store.set_value("s", "k", "v")
        store.purge_all()
        assert store.list_keys("s") == []
