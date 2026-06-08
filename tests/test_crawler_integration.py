"""
Integration tests for CheerioCrawler — real HTTP requests against
quotes.toscrape.com (a public scraping practice site).
Tests the full stack: queue → fetch → parse → dataset → export.
"""

import pytest
from knowscraper.core.configuration import Configuration
from knowscraper.core.dataset import Dataset
from knowscraper.core.request import Request
from knowscraper.core.request_queue import RequestQueue
from knowscraper.crawlers.cheerio_crawler import CheerioCrawler
from knowscraper.core.router import Router


def make_crawler(tmp_path, router, dataset, **kwargs):
    """CheerioCrawler with fully isolated storage — no shared queue between tests."""
    config = Configuration(storage_dir=str(tmp_path / ".knowscraper"))
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        configuration=config,
        use_anti_detection=False,
        **kwargs,
    )
    crawler.request_queue = RequestQueue(db_path=str(tmp_path / "queue.db"))
    return crawler


@pytest.mark.asyncio
async def test_cheerio_scrapes_single_page(tmp_path):
    dataset = Dataset(name="test_single", storage_dir=str(tmp_path))
    router = Router()

    @router.default_handler
    async def handler(ctx):
        for quote in ctx.parsed.select(".quote"):
            text = quote.select_one(".text")
            if text:
                await dataset.push_data({"quote": text.get_text(strip=True)})

    crawler = make_crawler(tmp_path, router, dataset, max_concurrency=1)
    await crawler.run(["https://quotes.toscrape.com"])

    assert dataset.count == 10  # 10 quotes per page


@pytest.mark.asyncio
async def test_cheerio_follows_pagination(tmp_path):
    dataset = Dataset(name="test_pagination", storage_dir=str(tmp_path))
    router = Router()

    @router.default_handler
    async def handler(ctx):
        for quote in ctx.parsed.select(".quote"):
            text = quote.select_one(".text")
            if text:
                await dataset.push_data({"quote": text.get_text(strip=True)})
        await ctx.enqueue_links(selector="li.next a")

    crawler = make_crawler(tmp_path, router, dataset, max_concurrency=2)
    await crawler.run(["https://quotes.toscrape.com"])

    assert dataset.count == 100  # 10 pages × 10 quotes


@pytest.mark.asyncio
async def test_label_based_routing(tmp_path):
    dataset = Dataset(name="test_labels", storage_dir=str(tmp_path))
    router = Router()
    visited_labels = []

    @router.handler("listing")
    async def listing(ctx):
        visited_labels.append("listing")
        await ctx.enqueue_links(selector="a[href*='/author/']", label="author")

    @router.handler("author")
    async def author(ctx):
        visited_labels.append("author")
        name = ctx.parsed.select_one("h1")
        if name:
            await dataset.push_data({"author": name.get_text(strip=True)})

    crawler = make_crawler(tmp_path, router, dataset, max_concurrency=3)
    start = Request(url="https://quotes.toscrape.com", label="listing")
    await crawler.add_requests([start])
    await crawler.run()

    assert "listing" in visited_labels
    assert "author" in visited_labels
    assert dataset.count > 0


@pytest.mark.asyncio
async def test_retry_on_failure(tmp_path):
    dataset = Dataset(name="test_retry", storage_dir=str(tmp_path))
    router = Router()
    attempt_counts = []

    @router.default_handler
    async def handler(ctx):
        attempt_counts.append(1)
        if len(attempt_counts) < 2:
            raise RuntimeError("Simulated failure")
        await dataset.push_data({"ok": True})

    crawler = make_crawler(tmp_path, router, dataset, max_concurrency=1, max_request_retries=3)
    await crawler.run(["https://quotes.toscrape.com"])

    assert len(attempt_counts) == 2
    assert dataset.count == 1


@pytest.mark.asyncio
async def test_stats_reported(tmp_path):
    dataset = Dataset(name="test_stats", storage_dir=str(tmp_path))
    router = Router()

    @router.default_handler
    async def handler(ctx):
        pass

    crawler = make_crawler(tmp_path, router, dataset)
    stats = await crawler.run(["https://quotes.toscrape.com"])

    assert stats["requests_done"] >= 1
    assert stats["requests_failed"] == 0
    assert stats["start_time"] > 0
    assert stats["end_time"] > stats["start_time"]


@pytest.mark.asyncio
async def test_export_csv_after_crawl(tmp_path):
    dataset = Dataset(name="test_csv", storage_dir=str(tmp_path))
    router = Router()

    @router.default_handler
    async def handler(ctx):
        for q in ctx.parsed.select(".quote .text"):
            await dataset.push_data({"text": q.get_text(strip=True)})

    crawler = make_crawler(tmp_path, router, dataset)
    await crawler.run(["https://quotes.toscrape.com"])

    csv_path = await dataset.export_to_csv()
    assert csv_path.exists()
    lines = csv_path.read_text().strip().splitlines()
    assert len(lines) == 11  # header + 10 quotes
