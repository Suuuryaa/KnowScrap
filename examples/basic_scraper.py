"""
KnowScraper - Basic example
Scrapes quotes from quotes.toscrape.com — a safe practice site.
Demonstrates: CheerioCrawler + Router + enqueue_links + Dataset
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from knowscraper import CheerioCrawler, Router, Dataset, Request

router = Router()
dataset = Dataset(name="quotes")


@router.default_handler
async def handle_listing(ctx):
    ctx.log.info(f"Scraping: {ctx.request.url}")

    # Extract all quotes
    for quote in ctx.parsed.select(".quote"):
        text = quote.select_one(".text")
        author = quote.select_one(".author")
        tags = [t.get_text() for t in quote.select(".tag")]

        if text and author:
            await dataset.push_data({
                "quote": text.get_text(strip=True),
                "author": author.get_text(strip=True),
                "tags": tags,
                "source_url": ctx.request.url,
            })

    # Follow "Next" button
    await ctx.enqueue_links(selector="li.next a", label="listing")

    count = dataset.count
    ctx.log.info(f"Total quotes collected so far: {count}")


async def main():
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=3,
        min_delay=0.5,
        max_delay=1.5,
        use_anti_detection=False,  # set True to use Node.js TLS fingerprinting
    )

    await crawler.run(["https://quotes.toscrape.com"])

    # Export results
    csv_path = await dataset.export_to_csv()
    json_path = await dataset.export_to_json()

    print(f"\nDone! Collected {dataset.count} quotes")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
