# KnowScraper

<img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
<img src="https://img.shields.io/badge/node.js-18%2B-brightgreen" alt="Node.js 18+">
<img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
<img src="https://img.shields.io/badge/tests-211%20passing-success" alt="Tests">

**KnowScraper is a reliable web scraping framework for Python.**

It handles HTTP crawling, browser automation, anti-bot evasion, and data storage — so you can focus on your data, not infrastructure. Inspired by [Crawlee](https://crawlee.dev), built for Python.

```python
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
    await ctx.enqueue_links(selector="li.next a")

crawler = CheerioCrawler(router=router, dataset=dataset, use_anti_detection=True)
await crawler.run(["https://quotes.toscrape.com"])
await dataset.export_to_csv()
```

## Installation

```bash
pip install knowscraper
playwright install chromium   # only for browser crawlers
```

Requires Python 3.10+ and Node.js 18+.

## Features

- **Anti-bot evasion** — Chrome TLS fingerprints via `got-scraping`, browser fingerprint injection, stealth JS patches, human-like mouse/scroll/type
- **6 crawler types** — HTTP, Cheerio (BS4), Playwright, Puppeteer, Adaptive (auto-detects JS), AI-powered
- **Persistent queue** — SQLite-backed, survives crashes, resumes exactly where it stopped
- **Smart concurrency** — autoscales based on CPU and memory in real time
- **Session & proxy rotation** — each "user" gets its own cookies, headers, and IP
- **Plugin system** — `DedupPlugin`, `RetryPlugin`, `StatsPlugin`, `LoggingPlugin`, or build your own
- **CAPTCHA solving** — detects reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile; solves via 2captcha or CapSolver
- **AI extraction** — describe what you want in plain English, Claude extracts it
- **Sitemap support** — discover and parse XML sitemaps with lastmod filtering
- **robots.txt** + per-domain rate limiting built in
- **CSV & JSON export** out of the box

## Crawlers

| Crawler | JS | Anti-bot | Best for |
|---|---|---|---|
| `HttpCrawler` | ✗ | TLS fingerprint | APIs, raw HTTP |
| `CheerioCrawler` | ✗ | TLS fingerprint | Static HTML sites |
| `PlaywrightCrawler` | ✓ | Full fingerprint + stealth | SPAs, JS-heavy sites |
| `PuppeteerCrawler` | ✓ | Full fingerprint | Puppeteer-specific workflows |
| `AdaptiveCrawler` | Auto | Both | Mixed sites |
| `AICrawler` | ✓ | Full fingerprint | No-selector AI extraction |

## Example — PlaywrightCrawler

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
    stealth_mode=True,
    inject_fingerprint=True,
    random_interactions=True,
)
await crawler.run(["https://example.com"])
```

## Example — AICrawler (no selectors)

```python
from knowscraper import AICrawler, Router, Dataset

router  = Router()
dataset = Dataset(name="products")

@router.default_handler
async def handler(ctx):
    data = await ctx.extract("product name, price, and rating")
    await dataset.push_data(data)

crawler = AICrawler(router=router, dataset=dataset)
# Set ANTHROPIC_API_KEY env var or pass api_key=
await crawler.run(["https://example.com/products"])
```

## Example — Label routing

```python
@router.handler("listing")
async def on_listing(ctx):
    await ctx.enqueue_links(selector="a.product", label="product")
    await ctx.enqueue_links(selector="a.next",    label="listing")

@router.handler("product")
async def on_product(ctx):
    await dataset.push_data({
        "name":  ctx.parsed.select_one("h1").get_text(strip=True),
        "price": ctx.parsed.select_one(".price").get_text(strip=True),
    })
```

## Example — Plugins

```python
from knowscraper import DedupPlugin, RetryPlugin, StatsPlugin

stats   = StatsPlugin()
crawler = CheerioCrawler(
    router=router,
    plugins=[DedupPlugin(key="url"), RetryPlugin(base_delay=2.0), stats],
)
await crawler.run(["https://example.com"])
print(stats.report())
```

## CLI

```bash
knowscraper create my-project                  # scaffold HTTP scraper
knowscraper create my-project --type playwright  # scaffold browser scraper
knowscraper run main.py                        # run a scraper
knowscraper info                               # show version + environment
```

## Architecture

KnowScraper uses a Python + Node.js hybrid. The Node.js microservice starts automatically and handles TLS fingerprinting and browser fingerprints.

```
Python                           Node.js (localhost:9119)
──────────────────────           ───────────────────────────
CheerioCrawler                   got-scraping  (Chrome TLS)
PlaywrightCrawler    ←──────→    header-generator
PuppeteerCrawler                 fingerprint-generator
Router / Dataset                 fingerprint-injector
SessionPool / Queue              Puppeteer
```

## License

MIT © [Suuuryaa](https://github.com/Suuuryaa)
