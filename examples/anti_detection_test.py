"""
KnowScraper - Anti-Detection Test
Full stack: Python orchestration + Node.js TLS fingerprinting via got-scraping.
The Node service auto-starts, all HTTP goes through real Chrome TLS.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from knowscraper import CheerioCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="anti_detect_quotes")


@router.default_handler
async def handle_page(ctx):
    ctx.log.info(f"[got-scraping TLS] {ctx.request.url}")

    for quote in ctx.parsed.select(".quote"):
        text = quote.select_one(".text")
        author = quote.select_one(".author")
        tags = [t.get_text() for t in quote.select(".tag")]
        if text and author:
            await dataset.push_data({
                "quote": text.get_text(strip=True),
                "author": author.get_text(strip=True),
                "tags": tags,
            })

    await ctx.enqueue_links(selector="li.next a")


async def main():
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=3,
        min_delay=0.3,
        max_delay=1.0,
        use_anti_detection=True,   # <-- Node.js got-scraping TLS fingerprinting ON
    )

    stats = await crawler.run(["https://quotes.toscrape.com"])

    csv_path = await dataset.export_to_csv()
    json_path = await dataset.export_to_json()

    print(f"\n{'='*50}")
    print(f"KnowScraper Anti-Detection Test — COMPLETE")
    print(f"{'='*50}")
    print(f"Quotes collected : {dataset.count}")
    print(f"Pages scraped    : {stats['requests_done']}")
    print(f"Failed requests  : {stats['requests_failed']}")
    print(f"CSV output       : {csv_path}")
    print(f"JSON output      : {json_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
