# KnowScraper

**Knowledge Scraper Framework** — A production-grade web scraping framework inspired by [Crawlee](https://crawlee.dev).

Python core + Node.js anti-detection. Built for reliability, scale, and stealth.

---

## What it does

KnowScraper handles everything hard about web scraping so you can focus on your data:

- **Anti-bot evasion** — real Chrome TLS fingerprints, browser fingerprint injection, stealth JS patches
- **Smart concurrency** — autoscales based on CPU/memory in real time
- **Session & proxy rotation** — each "user" has its own cookies, headers, and proxy
- **Persistent queue** — SQLite-backed, survives crashes, resumes where it left off
- **Deduplication** — never visits the same URL twice
- **Automatic retries** — configurable retry count with exponential backoff
- **robots.txt enforcement** — respects crawl rules and Crawl-delay directives
- **Per-domain rate limiting** — don't hammer servers even with high concurrency
- **Label-based routing** — different handlers for different page types
- **CSV & JSON export** — clean output, ready to use

---

## Architecture

```
Python (core brain)              Node.js (anti-detection)
────────────────────             ────────────────────────
RequestQueue (SQLite)            got-scraping (TLS fingerprint)
SessionPool                      header-generator
ProxyRotator                     fingerprint-generator
AutoscaledPool (CPU/mem)         fingerprint-injector
Router (label dispatch)
Dataset (storage + export)
CheerioCrawler (HTTP + BS4)
PlaywrightCrawler (browser)
AdaptiveCrawler (auto-detect)
```

---

## Quick Start

### Install

```bash
pip install knowscraper
playwright install chromium   # only if using PlaywrightCrawler
```

### Scaffold a new project

```bash
# HTTP crawler (fast, no browser)
knowscraper create my-scraper

# Browser crawler (JS-heavy sites)
knowscraper create my-scraper --type playwright

cd my-scraper
python main.py
```

---

## Examples

### CheerioCrawler — scrape a static site

```python
import asyncio
from knowscraper import CheerioCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="quotes")

@router.default_handler
async def handle_page(ctx):
    for quote in ctx.parsed.select(".quote"):
        text = quote.select_one(".text")
        author = quote.select_one(".author")
        if text and author:
            await dataset.push_data({
                "quote": text.get_text(strip=True),
                "author": author.get_text(strip=True),
            })
    # follow "Next" button automatically
    await ctx.enqueue_links(selector="li.next a")

async def main():
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=5,
        min_delay=0.5,
        max_delay=1.5,
        respect_robots_txt=True,
        use_anti_detection=True,   # Chrome TLS fingerprinting via Node.js
    )
    await crawler.run(["https://quotes.toscrape.com"])
    await dataset.export_to_csv()

asyncio.run(main())
```

### PlaywrightCrawler — scrape a JavaScript-heavy site

```python
import asyncio
from knowscraper import PlaywrightCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="spa_data")

@router.default_handler
async def handle_page(ctx):
    # Full Playwright page object
    title = await ctx.page.title()
    content = await ctx.page.inner_text("body")
    await dataset.push_data({"title": title, "url": ctx.request.url})

async def main():
    crawler = PlaywrightCrawler(
        router=router,
        dataset=dataset,
        browser_type="chromium",
        headless=True,
        stealth_mode=True,         # JS patches (removes webdriver flag, etc.)
        inject_fingerprint=True,   # real browser fingerprints from Node.js
        random_interactions=True,  # human-like mouse movement + scrolling
        use_anti_detection=True,
    )
    await crawler.run(["https://example.com"])

asyncio.run(main())
```

### Label-based routing — different handlers per page type

```python
from knowscraper import CheerioCrawler, Router, Dataset, Request

router = Router()
dataset = Dataset(name="products")

@router.handler("listing")
async def handle_listing(ctx):
    # enqueue product links with "product" label
    await ctx.enqueue_links(selector="a.product-link", label="product")
    # enqueue next page
    await ctx.enqueue_links(selector="a.next-page", label="listing")

@router.handler("product")
async def handle_product(ctx):
    name  = ctx.parsed.select_one("h1.product-name")
    price = ctx.parsed.select_one(".price")
    await dataset.push_data({
        "name":  name.get_text(strip=True) if name else "",
        "price": price.get_text(strip=True) if price else "",
        "url":   ctx.request.url,
    })

async def main():
    crawler = CheerioCrawler(router=router, dataset=dataset)
    start = Request(url="https://example-shop.com/products", label="listing")
    await crawler.add_requests([start])
    await crawler.run()

asyncio.run(main())
```

### Proxy rotation + session pool

```python
from knowscraper import CheerioCrawler, ProxyConfiguration

proxy_config = ProxyConfiguration(
    proxy_urls=[
        "http://user:pass@proxy1.example.com:8080",
        "http://user:pass@proxy2.example.com:8080",
        "http://user:pass@proxy3.example.com:8080",
    ],
    rotate="round_robin",  # or "random"
)

crawler = CheerioCrawler(
    router=router,
    proxy_configuration=proxy_config,
    max_concurrency=10,
)
```

### Resume a crashed crawl

```python
# First run — crawls normally
await crawler.run(["https://example.com"])

# Second run — resumes from where it stopped
await crawler.run(resume=True)
```

### robots.txt + rate limiting

```python
crawler = CheerioCrawler(
    router=router,
    respect_robots_txt=True,        # skip URLs disallowed by robots.txt
    user_agent="MyBot/1.0",
    max_requests_per_minute=30,     # never exceed 30 req/min per domain
)
```

---

## Crawler types

| Crawler | Speed | Handles JS | Best for |
|---|---|---|---|
| `CheerioCrawler` | Very fast | No | Static HTML sites |
| `HttpCrawler` | Very fast | No | Raw HTTP, APIs |
| `PlaywrightCrawler` | Slower | Yes | SPAs, JS-heavy sites |
| `AdaptiveCrawler` | Smart | Auto | Mixed sites |

---

## Configuration

All settings configurable via constructor args or environment variables:

```bash
KNOWSCRAPER_MAX_CONCURRENCY=10
KNOWSCRAPER_MIN_CONCURRENCY=1
KNOWSCRAPER_REQUEST_TIMEOUT=30
KNOWSCRAPER_MAX_RETRIES=3
KNOWSCRAPER_MIN_DELAY=0.5
KNOWSCRAPER_MAX_DELAY=2.0
KNOWSCRAPER_HEADLESS=true
KNOWSCRAPER_BROWSER=chromium
KNOWSCRAPER_LOG_LEVEL=INFO
KNOWSCRAPER_STORAGE_DIR=.knowscraper
KNOWSCRAPER_NODE_SERVICE=http://127.0.0.1:9119
```

---

## Output

All data saved to `.knowscraper/datasets/<name>/`:

```python
# Export after crawl
await dataset.export_to_csv()    # → .knowscraper/datasets/results/data.csv
await dataset.export_to_json()   # → .knowscraper/datasets/results/data.json

# Read programmatically
records = await dataset.get_data(offset=0, limit=100)
async for record in dataset.iterate():
    print(record)
```

---

## Anti-Detection Stack

KnowScraper uses a Python + Node.js hybrid for maximum anti-detection:

```
Request
  → Session (cookies + identity)
  → Proxy (IP rotation)
  → got-scraping (Chrome TLS fingerprint)     ← Node.js
  → header-generator (realistic headers)      ← Node.js
  → fingerprint-injector (browser props)      ← Node.js
  → Playwright stealth patches                ← Python
  → Human-like interactions (optional)        ← Python
```

The Node.js anti-detection service starts automatically when `use_anti_detection=True`.

---

## Project Structure

```
src/knowscraper/
├── core/
│   ├── request.py             # Request object + state machine
│   ├── request_queue.py       # SQLite-backed queue + deduplication
│   ├── router.py              # Label routing + CrawlingContext
│   ├── dataset.py             # Output storage + CSV/JSON export
│   ├── configuration.py       # Global config (env var overrides)
│   ├── session_pool.py        # Session lifecycle management
│   ├── proxy_configuration.py # Proxy rotation
│   └── autoscaled_pool.py     # Dynamic concurrency (CPU/memory)
│
├── crawlers/
│   ├── base_crawler.py        # Abstract base (run loop, retries, robots, rate limit)
│   ├── http_crawler.py        # Plain HTTP via got-scraping
│   ├── cheerio_crawler.py     # HTTP + BeautifulSoup
│   ├── playwright_crawler.py  # Real browser + fingerprints + stealth
│   └── adaptive_crawler.py   # Auto HTTP→browser upgrade
│
├── anti_detection/
│   ├── stealth.py             # JS patches + human mouse/scroll/type
│   ├── bridge.py              # Python ↔ Node.js communication
│   └── node_service/
│       ├── server.js          # Express microservice
│       └── package.json
│
├── storage/
│   └── local_storage.py       # Filesystem storage backend
│
└── utils/
    ├── url_utils.py           # URL normalization + extraction
    ├── robots.py              # robots.txt fetching + enforcement
    └── log.py                 # Loguru logger
```

---

## CLI Reference

```bash
knowscraper create <name>                  # scaffold HTTP scraper project
knowscraper create <name> --type playwright  # scaffold browser scraper project
knowscraper run <file.py>                  # run a scraper file
knowscraper info                           # show version + environment
```

---

## License

MIT
