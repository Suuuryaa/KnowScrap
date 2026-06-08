"""
KnowScraper — Live Demo
Scrapes quotes.toscrape.com (a site built for scraper demos)
Shows: routing, pagination, dedup, stats, CSV export
"""

import asyncio
import time
from knowscraper import CheerioCrawler, Router, Dataset, Request
from knowscraper import DedupPlugin, StatsPlugin, LoggingPlugin

# ── fancy terminal output ──────────────────────────────────────────────────────

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
PURPLE = "\033[95m"

def banner():
    print(f"""
{CYAN}{BOLD}
  ██╗  ██╗███╗   ██╗ ██████╗ ██╗    ██╗███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗██████╗
  ██║ ██╔╝████╗  ██║██╔═══██╗██║    ██║██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
  █████╔╝ ██╔██╗ ██║██║   ██║██║ █╗ ██║███████╗██║     ██████╔╝███████║██████╔╝█████╗  ██████╔╝
  ██╔═██╗ ██║╚██╗██║██║   ██║██║███╗██║╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗
  ██║  ██╗██║ ╚████║╚██████╔╝╚███╔███╔╝███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝
{RESET}""")
    print(f"  {DIM}A Crawlee-inspired web scraping framework for Python{RESET}")
    print(f"  {DIM}Python core · Node.js anti-detection · Anti-bot evasion{RESET}\n")
    print(f"  {YELLOW}▶  Demo: scraping quotes.toscrape.com{RESET}")
    print(f"  {DIM}   Label routing · Pagination · Dedup · Stats · CSV export{RESET}\n")
    print(f"  {'─' * 70}\n")

# ── setup ──────────────────────────────────────────────────────────────────────

router  = Router()
dataset = Dataset(name="quotes_demo")
stats   = StatsPlugin()

# ── handlers ───────────────────────────────────────────────────────────────────

@router.handler("listing")
async def handle_listing(ctx):
    quotes = ctx.parsed.select(".quote")
    print(f"  {CYAN}[listing]{RESET}  {ctx.request.url}")
    print(f"  {DIM}          Found {len(quotes)} quotes on this page{RESET}")

    for quote in quotes:
        text   = quote.select_one(".text")
        author = quote.select_one(".author")
        tags   = [t.get_text(strip=True) for t in quote.select(".tag")]
        if text and author:
            await dataset.push_data({
                "quote":  text.get_text(strip=True).strip('"'),
                "author": author.get_text(strip=True),
                "tags":   ", ".join(tags),
                "url":    ctx.request.url,
            })

    # follow Next page
    await ctx.enqueue_links(selector="li.next a", label="listing")


@router.handler("author")
async def handle_author(ctx):
    name  = ctx.parsed.select_one("h3.author-title")
    born  = ctx.parsed.select_one(".author-born-date")
    desc  = ctx.parsed.select_one(".author-description")
    print(f"  {PURPLE}[author]{RESET}   {ctx.request.url}")
    if name:
        print(f"  {DIM}          → {name.get_text(strip=True)}{RESET}")


# ── main ───────────────────────────────────────────────────────────────────────

async def main():
    banner()

    print(f"  {GREEN}✓{RESET} Plugins loaded: {BOLD}DedupPlugin · StatsPlugin · LoggingPlugin{RESET}")
    print(f"  {GREEN}✓{RESET} Anti-detection: {BOLD}Chrome TLS fingerprint via Node.js{RESET}")
    print(f"  {GREEN}✓{RESET} Queue backend:  {BOLD}SQLite (persistent){RESET}")
    print(f"  {GREEN}✓{RESET} Concurrency:    {BOLD}autoscaled (CPU + memory){RESET}\n")
    print(f"  {'─' * 70}\n")

    t0 = time.time()

    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=3,
        min_delay=0.3,
        max_delay=0.8,
        respect_robots_txt=True,
        use_anti_detection=False,   # set True if Node.js service is running
        plugins=[
            DedupPlugin(key="quote"),
            stats,
        ],
    )

    await crawler.run([
        Request(url="https://quotes.toscrape.com", label="listing"),
    ])

    elapsed = time.time() - t0

    # ── results ────────────────────────────────────────────────────────────────
    print(f"\n  {'─' * 70}\n")
    print(f"  {GREEN}{BOLD}✓ Crawl complete!{RESET}\n")

    report = stats.report()
    print(f"  {BOLD}Stats:{RESET}")
    print(f"    Requests finished : {GREEN}{crawler.stats['requests_done']}{RESET}")
    print(f"    Data records saved: {GREEN}{dataset.count}{RESET}")
    print(f"    Avg response time : {GREEN}{report['avg_response_time']}s{RESET}")
    print(f"    Total time        : {GREEN}{elapsed:.1f}s{RESET}")

    # show a few sample records
    records = await dataset.get_data(limit=3)
    print(f"\n  {BOLD}Sample records:{RESET}")
    for r in records:
        print(f"    {CYAN}\"{r['quote'][:60]}...\"{RESET}")
        print(f"    {DIM}— {r['author']}   tags: {r['tags']}{RESET}\n")

    # export
    csv_path  = await dataset.export_to_csv()
    json_path = await dataset.export_to_json()
    print(f"  {GREEN}✓{RESET} Exported to {BOLD}{csv_path}{RESET}")
    print(f"  {GREEN}✓{RESET} Exported to {BOLD}{json_path}{RESET}\n")

asyncio.run(main())
