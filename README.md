<h1 align="center">
  KnowScraper
</h1>

<p align="center">
  <b>Reliable web scraping for Python — with real anti-bot evasion built in.</b><br>
  Python core · Node.js anti-detection · Crawlee-inspired
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/node.js-18%2B-339933?logo=node.js&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-22c55e" />
  <img src="https://img.shields.io/badge/tests-211%20passing-22c55e" />
  <img src="https://img.shields.io/badge/playwright-supported-e2e" />
</p>

---

KnowScraper handles the hard parts of web scraping — bot detection, retries, concurrency, deduplication, storage — so you write handlers, not infrastructure.

```python
import asyncio
from knowscraper import CheerioCrawler, Router, Dataset

router  = Router()
dataset = Dataset(name="quotes")

@router.default_handler
async def handler(ctx):
    for q in ctx.parsed.select(".quote"):
        await dataset.push_data({
            "text":   q.select_one(".text").get_text(strip=True),
            "author": q.select_one(".author").get_text(strip=True),
        })
    await ctx.enqueue_links(selector="li.next a")   # follow pagination

async def main():
    crawler = CheerioCrawler(
        router=router,
        dataset=dataset,
        max_concurrency=5,
        respect_robots_txt=True,
        use_anti_detection=True,   # Chrome TLS fingerprint via Node.js
    )
    await crawler.run(["https://quotes.toscrape.com"])
    await dataset.export_to_csv()

asyncio.run(main())
```

## Installation

```bash
pip install knowscraper
playwright install chromium   # only needed for browser crawlers
```

> Requires Python 3.10+ and Node.js 18+

---

## What's included

| | Feature |
|---|---|
| 🛡️ | **Anti-bot** — Chrome TLS fingerprints, browser fingerprint injection, stealth JS patches, human-like mouse/scroll/type |
| 🌐 | **6 crawlers** — HTTP, Cheerio, Playwright, Puppeteer, Adaptive (auto-detects JS), AI-powered |
| 🔄 | **Persistent queue** — SQLite-backed, survives crashes, resumes where it stopped |
| ⚡ | **Smart concurrency** — autoscales based on CPU + memory |
| 🔀 | **Session & proxy rotation** — each request gets its own identity and IP |
| 🤖 | **AI extraction** — describe what you want, Claude extracts it (no selectors) |
| 🧩 | **Plugins** — `DedupPlugin`, `RetryPlugin`, `StatsPlugin`, `LoggingPlugin` |
| 🔒 | **CAPTCHA solving** — reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile |
| 🗺️ | **Sitemaps** — discover and crawl XML sitemaps with lastmod filtering |
| 📦 | **Export** — CSV and JSON out of the box |

---

## Crawlers

| Crawler | JS rendering | Anti-bot | Use when |
|---|---|---|---|
| `CheerioCrawler` | ✗ | TLS fingerprint | Static sites, blogs, e-commerce |
| `HttpCrawler` | ✗ | TLS fingerprint | APIs, raw HTTP |
| `PlaywrightCrawler` | ✓ | Full fingerprint + stealth | SPAs, React/Vue/Angular apps |
| `PuppeteerCrawler` | ✓ | Full fingerprint | Puppeteer-specific workflows |
| `AdaptiveCrawler` | Auto | Both | Mixed sites — upgrades automatically |
| `AICrawler` | ✓ | Full fingerprint | Extract data without writing selectors |

---

## Examples

<details>
<summary><b>PlaywrightCrawler — JavaScript-heavy site</b></summary>

```python
from knowscraper import PlaywrightCrawler, Router, Dataset

router  = Router()
dataset = Dataset(name="results")

@router.default_handler
async def handler(ctx):
    title = await ctx.page.title()
    await dataset.push_data({"title": title, "url": ctx.request.url})

crawler = PlaywrightCrawler(
    router=router,
    dataset=dataset,
    stealth_mode=True,          # removes webdriver flag, spoofs plugins
    inject_fingerprint=True,    # real Chrome fingerprint via Node.js
    random_interactions=True,   # human-like mouse + scroll
)
await crawler.run(["https://example.com"])
```
</details>

<details>
<summary><b>AICrawler — no selectors needed</b></summary>

```python
from knowscraper import AICrawler, Router, Dataset

router  = Router()
dataset = Dataset(name="products")

@router.default_handler
async def handler(ctx):
    # plain English — Claude reads the page and extracts the data
    data = await ctx.extract("product name, price, rating, and availability")
    await dataset.push_data(data)

    # also works for actions
    await ctx.act("click the Accept Cookies button if it exists")

crawler = AICrawler(router=router, dataset=dataset)
# set ANTHROPIC_API_KEY or pass api_key="sk-ant-..."
await crawler.run(["https://example.com/products"])
```
</details>

<details>
<summary><b>Label-based routing — listings + product pages</b></summary>

```python
from knowscraper import CheerioCrawler, Router, Dataset, Request

router  = Router()
dataset = Dataset(name="products")

@router.handler("listing")
async def on_listing(ctx):
    await ctx.enqueue_links(selector="a.product-link", label="product")
    await ctx.enqueue_links(selector="a.next-page",    label="listing")

@router.handler("product")
async def on_product(ctx):
    await dataset.push_data({
        "name":  ctx.parsed.select_one("h1").get_text(strip=True),
        "price": ctx.parsed.select_one(".price").get_text(strip=True),
        "url":   ctx.request.url,
    })

crawler = CheerioCrawler(router=router, dataset=dataset)
await crawler.run([Request(url="https://shop.example.com", label="listing")])
```
</details>

<details>
<summary><b>Plugins — dedup, retry, stats</b></summary>

```python
from knowscraper import CheerioCrawler, DedupPlugin, RetryPlugin, StatsPlugin

stats   = StatsPlugin()
crawler = CheerioCrawler(
    router=router,
    plugins=[
        DedupPlugin(key="url"),       # drop duplicate records before saving
        RetryPlugin(base_delay=2.0),  # exponential backoff: 2s, 4s, 8s...
        stats,
    ],
)
await crawler.run(["https://example.com"])
print(stats.report())
# {"requests_by_domain": {...}, "avg_response_time": 0.3, "data_records_saved": 42}
```
</details>

<details>
<summary><b>Proxy rotation + session pool</b></summary>

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
</details>

<details>
<summary><b>Resume a crashed crawl</b></summary>

```python
# First run — crawls normally
await crawler.run(["https://example.com"])

# Restart — picks up exactly where it stopped (SQLite queue persists)
await crawler.run(resume=True)
```
</details>

<details>
<summary><b>Sitemap discovery</b></summary>

```python
from knowscraper import fetch_sitemap_urls
from datetime import datetime

urls = await fetch_sitemap_urls(
    "https://example.com",
    modified_after=datetime(2024, 1, 1),
    max_urls=500,
)
await crawler.run(urls)
```
</details>

---

## CLI

```bash
knowscraper create my-project                    # new HTTP scraper
knowscraper create my-project --type playwright  # new browser scraper
knowscraper run main.py                          # run a scraper file
knowscraper info                                 # version + environment
```

---

## How it works

KnowScraper runs a lightweight Node.js microservice alongside Python. It starts automatically and handles everything that requires matching Chrome's exact network behaviour.

```
Your code (Python)
     │
     ▼
 BaseCrawler — queue, retries, rate limiting, robots.txt
     │
     ├── CheerioCrawler / HttpCrawler
     │        └── Node.js service → got-scraping (Chrome TLS)
     │
     └── PlaywrightCrawler / PuppeteerCrawler
              ├── Node.js service → fingerprint-generator + injector
              └── Playwright → stealth patches + human interactions
```

---

## License

MIT © [Suuuryaa](https://github.com/Suuuryaa)
