"""Tests for RequestQueue — deduplication, state transitions, persistence."""

import asyncio
import os
import pytest
from knowscraper.core.request import Request, RequestState
from knowscraper.core.request_queue import RequestQueue


@pytest.fixture
def tmp_queue(tmp_path):
    q = RequestQueue(db_path=str(tmp_path / "test_queue.db"))
    yield q
    q.close()


@pytest.mark.asyncio
async def test_add_and_fetch(tmp_queue):
    req = Request(url="https://example.com")
    added = await tmp_queue.add_request(req)
    assert added is True

    fetched = await tmp_queue.fetch_next()
    assert fetched is not None
    assert fetched.url == "https://example.com"
    assert fetched.state == RequestState.IN_PROGRESS


@pytest.mark.asyncio
async def test_deduplication(tmp_queue):
    req = Request(url="https://example.com")
    first = await tmp_queue.add_request(req)
    second = await tmp_queue.add_request(req)
    assert first is True
    assert second is False  # duplicate rejected


@pytest.mark.asyncio
async def test_empty_queue_returns_none(tmp_queue):
    result = await tmp_queue.fetch_next()
    assert result is None


@pytest.mark.asyncio
async def test_mark_done(tmp_queue):
    req = Request(url="https://example.com")
    await tmp_queue.add_request(req)
    fetched = await tmp_queue.fetch_next()
    await tmp_queue.mark_done(fetched)

    stats = await tmp_queue.get_stats()
    assert stats.get("DONE", 0) == 1
    assert stats.get("IN_PROGRESS", 0) == 0


@pytest.mark.asyncio
async def test_mark_failed_retryable(tmp_queue):
    req = Request(url="https://example.com", max_retries=3)
    await tmp_queue.add_request(req)
    fetched = await tmp_queue.fetch_next()
    await tmp_queue.mark_failed(fetched)

    # Should be back as PENDING (still retryable)
    stats = await tmp_queue.get_stats()
    assert stats.get("PENDING", 0) == 1


@pytest.mark.asyncio
async def test_mark_failed_exhausted(tmp_queue):
    # max_retries=1 means one retry allowed: retry_count goes 0→1, then can_retry=False → FAILED
    req = Request(url="https://example.com", max_retries=1)
    await tmp_queue.add_request(req)

    fetched = await tmp_queue.fetch_next()
    await tmp_queue.mark_failed(fetched)  # retry_count=1, can_retry=False → FAILED immediately

    stats = await tmp_queue.get_stats()
    assert stats.get("FAILED", 0) == 1
    assert stats.get("PENDING", 0) == 0


@pytest.mark.asyncio
async def test_bulk_add(tmp_queue):
    reqs = [Request(url=f"https://example.com/page/{i}") for i in range(5)]
    added = await tmp_queue.add_requests(reqs)
    assert added == 5

    stats = await tmp_queue.get_stats()
    assert stats.get("PENDING", 0) == 5


@pytest.mark.asyncio
async def test_bulk_add_dedup(tmp_queue):
    reqs = [Request(url="https://example.com")] * 3
    added = await tmp_queue.add_requests(reqs)
    assert added == 1  # only first one accepted


@pytest.mark.asyncio
async def test_is_empty_true(tmp_queue):
    assert await tmp_queue.is_empty() is True


@pytest.mark.asyncio
async def test_is_empty_false(tmp_queue):
    await tmp_queue.add_request(Request(url="https://example.com"))
    assert await tmp_queue.is_empty() is False


@pytest.mark.asyncio
async def test_purge(tmp_queue):
    await tmp_queue.add_request(Request(url="https://example.com"))
    await tmp_queue.purge()
    assert await tmp_queue.is_empty() is True


@pytest.mark.asyncio
async def test_order_is_fifo(tmp_queue):
    urls = [f"https://example.com/{i}" for i in range(3)]
    for url in urls:
        await tmp_queue.add_request(Request(url=url))

    for expected_url in urls:
        req = await tmp_queue.fetch_next()
        assert req.url == expected_url
