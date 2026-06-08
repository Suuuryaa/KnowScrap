"""
KnowScraper - Browser example
Uses PlaywrightCrawler for JS-heavy sites.
Demonstrates: PlaywrightCrawler + page object + fingerprint injection
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from knowscraper import PlaywrightCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="spa_data")


@router.default_handler
async def handle_page(ctx):
    ctx.log.info(f"Browser visiting: {ctx.request.url}")

    # Use the Playwright page object directly
    title = await ctx.page.title()
    content = await ctx.page.inner_text("body")

    await dataset.push_data({
        "url": ctx.request.url,
        "title": title,
        "content_length": len(content),
    })

    # Follow links within same domain
    await ctx.enqueue_links(selector="a[href]")


async def main():
    crawler = PlaywrightCrawler(
        router=router,
        dataset=dataset,
        browser_type="chromium",
        headless=True,
        max_concurrency=2,
        inject_fingerprint=True,  # inject real browser fingerprints
        use_anti_detection=True,
    )

    await crawler.run(["https://quotes.toscrape.com/js"])
    print(f"\nDone! Collected {dataset.count} pages")


if __name__ == "__main__":
    asyncio.run(main())
