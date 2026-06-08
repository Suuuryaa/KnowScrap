# KnowScraper

<a href="https://pypi.org/project/knowscraper"><img src="https://img.shields.io/pypi/v/knowscraper?color=blue" alt="PyPI"></a>
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
<a href="https://github.com/Suuuryaa/KnowScrap/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
<a href="https://github.com/Suuuryaa/KnowScrap/actions"><img src="https://img.shields.io/github/actions/workflow/status/Suuuryaa/KnowScrap/scraper.yml?label=CI" alt="CI"></a>
<img src="https://img.shields.io/badge/Node.js-anti--detection-brightgreen" alt="Node.js">

> A Crawlee-inspired, production-grade web scraping framework for Python.  
> Python core · Node.js anti-detection · Built for reliability, scale, and stealth.

---

## Why KnowScraper?

Most scrapers break on real websites. KnowScraper doesn't — because it handles everything that makes scraping hard:

| Problem | KnowScraper solution |
|---|---|
| Bot detection (TLS fingerprint) | Chrome TLS via `got-scraping` (Node.js) |
| Bot detection (browser fingerprint) | `fingerprint-generator` + `fingerprint-injector` |
| Headless browser detection | Stealth JS patches, human mouse/scroll/type |
| IP bans | Proxy rotation with per-session identity |
| Crashes mid-crawl | SQLite queue — resumes exactly where it stopped |
| Duplicate URLs | SHA-256 deduplication built into the queue |
| Overloading servers | Per-domain rate limiting + autoscaled concurrency |
| JS-rendered pages | Playwright with full fingerprint injection |
| Boilerplate routing | Label-based Router — one handler per page type |

---

## Features

- **6 crawler types** — HTTP, Cheerio, Playwright, Puppeteer, Adaptive, AI-powered
- **Anti-bot stack** — Chrome TLS fingerprinting, browser fingerprints, stealth JS patches, human-like interactions
- **CAPTCHA handling** — detects and solves reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile
- **Sitemap support** — discover and parse XML sitemaps, sitemap indexes, gzipped sitemaps
- **Plugin ecosystem** — `DedupPlugin`, `RetryPlugin`, `StatsPlugin`, `LoggingPlugin` — or write your own
- **Memory storage** — drop-in in-memory queue/dataset for testing and lightweight runs
- **AI crawler** — Claude-powered extraction with natural language (`ctx.extract("product name and price")`)
- **KnowPlatform** — generate Dockerfile, docker-compose, and GitHub Actions workflows
- **Smart concurrency** — autoscales based on CPU and memory in real time
- **Session & proxy rotation** — each "user" has its own cookies, headers, and proxy
- **robots.txt enforcement** — respects crawl rules and `Crawl-delay` directives
- **Persistent queue** — SQLite-backed, survives crashes, resumes from where it stopped
- **Label-based routing** — different handlers for listing pages, product pages, pagination
- **CSV & JSON export** — clean output, ready to use

---

## Installation

```bash
pip install knowscraper

# Only needed for browser crawlers
playwright install chromium
```

**Requirements:** Python 3.10+, Node.js 18+

---

## Quick Start

### Scaffold a new project

```bash
# HTTP crawler (fast, no browser)
knowscraper create my-scraper

# Browser crawler (JS-heavy sites)
knowscraper create my-scraper --type playwright

cd my-scraper
python main.py
```

### Your first scraper

```python
import asyncio
from knowscraper import CheerioCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="quotes")

@router.default_handler
async def handle_page(ctx):
    for quote in ctx.parsed.select(".quote"):
        text   = quote.select_one(".text")
        author = quote.select_one(".author")
        if text and author:
            await dataset.push_data({
                "quote":  text.get_text(strip=True),
                "author": author.get_text(strip=True),
            })
    await ctx.enqueue_links(selector="li.next a")

async def main():
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=5,
        min_delay=0.5,
        max_delay=1.5,
        respect_robots_txt=True,
        use_anti_detection=True,
    )
    await crawler.run(["https://quotes.toscrape.com"])
    await dataset.export_to_csv()

asyncio.run(main())
```

---

## Crawler Types

| Crawler | Speed | JS | Anti-bot | Best for |
|---|---|---|---|---|
| `HttpCrawler` | ⚡⚡⚡ | ✗ | TLS fingerprint | Raw HTTP, APIs |
| `CheerioCrawler` | ⚡⚡⚡ | ✗ | TLS fingerprint | Static HTML sites |
| `PlaywrightCrawler` | ⚡⚡ | ✓ | Full fingerprint + stealth | SPAs, JS-heavy sites |
| `PuppeteerCrawler` | ⚡⚡ | ✓ | Full fingerprint | Puppeteer-specific workflows |
| `AdaptiveCrawler` | ⚡⚡⚡→⚡⚡ | Auto | Both | Mixed sites |
| `AICrawler` | ⚡ | ✓ | Full fingerprint | No-selector AI extraction |

---

## Examples

### PlaywrightCrawler — JavaScript-heavy site

```python
import asyncio
from knowscraper import PlaywrightCrawler, Router, Dataset

router = Router()
dataset = Dataset(name="spa_data")

@router.default_handler
async def handle_page(ctx):
    title   = await ctx.page.title()
    content = await ctx.page.inner_text("body")
    await dataset.push_data({"title": title, "url": ctx.request.url})

async def main():
    crawler = PlaywrightCrawler(
        router=router,
        dataset=dataset,
        stealth_mode=True,
        inject_fingerprint=True,
        random_interactions=True,   # human-like mouse + scroll
        use_anti_detection=True,
    )
    await crawler.run(["https://example.com"])

asyncio.run(main())
```

### AICrawler — no selectors needed

```python
import asyncio
from knowscraper import AICrawler, Router, Dataset

router = Router()
dataset = Dataset(name="products")

@router.default_handler
async def handle_page(ctx):
    # Describe what you want — Claude extracts it
    product = await ctx.extract("product name, price, rating, and availability")
    await dataset.push_data(product)

    # Natural language actions
    await ctx.act("click the Accept Cookies button if present")

async def main():
    crawler = AICrawler(
        router=router,
        dataset=dataset,
        # api_key="sk-ant-..."  or set ANTHROPIC_API_KEY env var
    )
    await crawler.run(["https://example.com/products"])

asyncio.run(main())
```

### Label-based routing

```python
from knowscraper import CheerioCrawler, Router, Dataset, Request

router  = Router()
dataset = Dataset(name="products")

@router.handler("listing")
async def handle_listing(ctx):
    await ctx.enqueue_links(selector="a.product-link", label="product")
    await ctx.enqueue_links(selector="a.next-page",    label="listing")

@router.handler("product")
async def handle_product(ctx):
    name  = ctx.parsed.select_one("h1.product-name")
    price = ctx.parsed.select_one(".price")
    await dataset.push_data({
        "name":  name.get_text(strip=True)  if name  else "",
        "price": price.get_text(strip=True) if price else "",
        "url":   ctx.request.url,
    })

async def main():
    crawler = CheerioCrawler(router=router, dataset=dataset)
    await crawler.run([Request(url="https://shop.example.com", label="listing")])

asyncio.run(main())
```

### Plugin ecosystem

```python
from knowscraper import CheerioCrawler, Router
from knowscraper import DedupPlugin, RetryPlugin, StatsPlugin, LoggingPlugin

stats  = StatsPlugin()
crawler = CheerioCrawler(
    router=router,
    plugins=[
        LoggingPlugin(),               # per-request timing logs
        DedupPlugin(key="url"),        # drop duplicate records
        RetryPlugin(base_delay=2.0),   # exponential backoff on retries
        stats,                         # collect per-domain metrics
    ],
)

await crawler.run(["https://example.com"])
print(stats.report())
# {
#   "requests_by_domain": {"example.com": 42},
#   "avg_response_time": 0.312,
#   "data_records_saved": 38,
#   ...
# }
```

### CAPTCHA handling

```python
from knowscraper import PlaywrightCrawler, Router
from knowscraper import CaptchaHandler

handler = CaptchaHandler(api_key="YOUR_2CAPTCHA_KEY", service="2captcha")

@router.default_handler
async def handle_page(ctx):
    solved = await handler.solve_and_inject(ctx.page)
    if solved:
        await ctx.page.click("#submit")
```

### Sitemap discovery

```python
from knowscraper import fetch_sitemap_urls
from datetime import datetime

urls = await fetch_sitemap_urls(
    "https://example.com",
    modified_after=datetime(2024, 1, 1),
    max_urls=1000,
)
await crawler.run(urls)
```

### Proxy rotation

```python
from knowscraper import CheerioCrawler, ProxyConfiguration

proxy_config = ProxyConfiguration(
    proxy_urls=[
        "http://user:pass@proxy1.example.com:8080",
        "http://user:pass@proxy2.example.com:8080",
    ],
    rotate="round_robin",
)

crawler = CheerioCrawler(router=router, proxy_configuration=proxy_config)
```

### Resume a crashed crawl

```python
# First run
await crawler.run(["https://example.com"])

# Resume from where it stopped (queue persists in SQLite)
await crawler.run(resume=True)
```

### Memory storage (for testing)

```python
from knowscraper.storage.memory_storage import MemoryRequestQueue, MemoryDataset

crawler = CheerioCrawler(router=router, dataset=MemoryDataset())
crawler.request_queue = MemoryRequestQueue()   # no disk, no SQLite
```

### Deploy with KnowPlatform

```python
from knowscraper import KnowPlatform, RunConfig

platform = KnowPlatform(project_dir=".")
platform.generate_dockerfile()        # production Dockerfile
platform.generate_docker_compose()    # local multi-container run
platform.generate_github_action()     # CI/CD workflow (daily cron + manual trigger)
platform.generate_input_schema()      # JSON schema for input validation

# In your scraper — works identically local and in Docker/CI
config = KnowPlatform.get_input()     # reads KNOWSCRAPER_INPUT env var
await crawler.run(config.start_urls)
```

---

## Architecture

```
Python (core)                        Node.js (anti-detection microservice)
─────────────────────────────        ──────────────────────────────────────
RequestQueue  (SQLite)               got-scraping      (Chrome TLS fingerprint)
SessionPool                          header-generator  (realistic HTTP headers)
ProxyConfiguration                   fingerprint-generator
AutoscaledPool (CPU/mem)             fingerprint-injector
Router (label dispatch)              Puppeteer         (headless Chrome via CDP)
Dataset (storage + export)
CheerioCrawler   (HTTP + BS4)
PlaywrightCrawler (browser)
PuppeteerCrawler  (Node.js browser)
AdaptiveCrawler  (auto HTTP→browser)
AICrawler        (Claude-powered)
```

The Node.js microservice starts automatically on `localhost:9119` when `use_anti_detection=True`.

---

## Project Structure

```
knowscraper/
├── src/knowscraper/
│   ├── core/
│   │   ├── request.py              # Request + state machine
│   │   ├── request_queue.py        # SQLite queue + deduplication
│   │   ├── router.py               # Label routing + CrawlingContext
│   │   ├── dataset.py              # Output storage, CSV/JSON export
│   │   ├── configuration.py        # Config + env var overrides
│   │   ├── session_pool.py         # Session lifecycle
│   │   ├── proxy_configuration.py  # Proxy rotation
│   │   └── autoscaled_pool.py      # Dynamic concurrency
│   │
│   ├── crawlers/
│   │   ├── base_crawler.py         # Run loop, retries, robots, rate limit
│   │   ├── http_crawler.py         # HTTP via got-scraping
│   │   ├── cheerio_crawler.py      # HTTP + BeautifulSoup
│   │   ├── playwright_crawler.py   # Real browser + stealth + fingerprints
│   │   ├── puppeteer_crawler.py    # Node.js Puppeteer via bridge
│   │   ├── adaptive_crawler.py     # Auto HTTP → browser upgrade
│   │   └── ai_crawler.py           # Claude-powered extraction + actions
│   │
│   ├── anti_detection/
│   │   ├── stealth.py              # JS patches + human mouse/scroll/type
│   │   ├── captcha.py              # CAPTCHA detection + solving
│   │   ├── bridge.py               # Python ↔ Node.js bridge
│   │   └── node_service/
│   │       ├── server.js           # Express microservice (TLS, fingerprint, Puppeteer)
│   │       └── package.json
│   │
│   ├── plugins/
│   │   ├── base_plugin.py          # Plugin base class (8 lifecycle hooks)
│   │   ├── plugin_manager.py       # Hook runner
│   │   └── builtin/
│   │       ├── logging_plugin.py
│   │       ├── dedup_plugin.py
│   │       ├── retry_plugin.py
│   │       └── stats_plugin.py
│   │
│   ├── storage/
│   │   ├── local_storage.py        # Filesystem backend
│   │   └── memory_storage.py       # In-memory backend (testing)
│   │
│   ├── utils/
│   │   ├── sitemap.py              # Sitemap discovery + parsing
│   │   ├── robots.py               # robots.txt enforcement
│   │   ├── url_utils.py            # URL normalization
│   │   └── log.py                  # Loguru logger
│   │
│   └── platform/
│       └── platform.py             # Dockerfile, CI, RunConfig
│
├── tests/                          # 211 tests
├── examples/
└── pyproject.toml
```

---

## Configuration

All settings can be passed as constructor arguments or set via environment variables:

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

# For Docker / CI runs
KNOWSCRAPER_INPUT='{"startUrls": ["https://example.com"], "maxPages": 100}'
ANTHROPIC_API_KEY=sk-ant-...   # for AICrawler
```

---

## Output

Data is saved to `.knowscraper/datasets/<name>/`:

```python
await dataset.export_to_csv()     # → .knowscraper/datasets/results/data.csv
await dataset.export_to_json()    # → .knowscraper/datasets/results/data.json

# Read programmatically
page   = await dataset.get_data(offset=0, limit=100)
async for record in dataset.iterate():
    print(record)
```

---

## CLI

```bash
knowscraper create <name>                    # scaffold HTTP scraper
knowscraper create <name> --type playwright  # scaffold browser scraper
knowscraper run <file.py>                    # run a scraper
knowscraper info                             # show version + environment
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/                           # all 211 tests
pytest tests/ -m "not integration"      # skip live network tests
```

---

## License

MIT © [Suuuryaa](https://github.com/Suuuryaa)
