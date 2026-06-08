"""
KnowScraper - AICrawler (KnowCrawler)
AI-powered web scraper using Claude (Anthropic) as the extraction brain.
Equivalent to Crawlee's StagehandCrawler.

Instead of writing CSS selectors, you describe what you want in plain English.
Claude reads the page and extracts exactly what you asked for.

Usage:
    crawler = AICrawler(
        api_key="sk-ant-...",
        router=router,
    )

    @router.default_handler
    async def handler(ctx):
        # Natural language extraction — no selectors needed
        data = await ctx.extract("product name, price, and rating")
        await dataset.push_data(data)

        # Natural language action
        await ctx.act("click the Add to Cart button")
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..core.request import Request
from ..core.router import CrawlingContext
from .playwright_crawler import PlaywrightCrawler


EXTRACT_SYSTEM_PROMPT = """You are a web scraping assistant.
You will be given HTML content and a description of what data to extract.
Respond ONLY with a valid JSON object containing the extracted data.
If a field cannot be found, use null.
Do not include any explanation — only the JSON object."""

ACT_SYSTEM_PROMPT = """You are a web scraping assistant.
You will be given HTML content and a description of an action to perform.
Respond with a JSON object containing:
  - "selector": CSS selector of the element to interact with
  - "action": "click" | "type" | "scroll" | "hover"
  - "text": text to type (only for "type" action)
If the action cannot be performed, respond with {"selector": null, "action": null}.
Do not include any explanation — only the JSON object."""


class AICrawlingContext(CrawlingContext):
    """
    Extended CrawlingContext with AI-powered extract() and act() methods.
    Wraps the standard context and adds Claude-based interaction.
    """

    def __init__(self, *args, api_key: str, model: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._api_key = api_key
        self._model = model

    async def extract(
        self,
        description: str,
        schema: dict | None = None,
    ) -> dict[str, Any]:
        """
        Extract structured data from the page using natural language.

        Args:
            description: What to extract, e.g. "product name, price, and description"
            schema: Optional JSON schema hint for the response shape

        Returns:
            dict with extracted fields

        Example:
            data = await ctx.extract("title, author, publication date, and summary")
        """
        html = await self._get_page_html()
        # Truncate very large pages — Claude has a context limit
        if len(html) > 80_000:
            soup = BeautifulSoup(html, "lxml")
            # Keep only meaningful content, strip scripts/styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            html = soup.get_text(separator="\n", strip=True)[:60_000]

        schema_hint = f"\n\nExpected JSON shape: {json.dumps(schema)}" if schema else ""
        prompt = f"""Extract the following from this web page:
{description}{schema_hint}

Page HTML/content:
{html}"""

        response = await self._call_claude(prompt, EXTRACT_SYSTEM_PROMPT)

        try:
            # Claude may wrap in ```json ... ```
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            return json.loads(clean.strip())
        except json.JSONDecodeError:
            return {"raw": response, "_parse_error": True}

    async def act(self, instruction: str) -> bool:
        """
        Perform an action on the page described in natural language.
        Only works with PlaywrightCrawler (requires ctx.page).

        Args:
            instruction: What to do, e.g. "click the login button"

        Returns:
            True if action was performed, False if not possible

        Example:
            await ctx.act("click the Accept Cookies button")
            await ctx.act("type 'hello world' into the search box")
        """
        if self.page is None:
            raise RuntimeError("act() requires a browser crawler (PlaywrightCrawler)")

        html = await self._get_page_html()
        if len(html) > 40_000:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style"]):
                tag.decompose()
            html = str(soup)[:40_000]

        prompt = f"""Page HTML:
{html}

Instruction: {instruction}"""

        response = await self._call_claude(prompt, ACT_SYSTEM_PROMPT)

        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            action_data = json.loads(clean.strip())
        except json.JSONDecodeError:
            return False

        selector = action_data.get("selector")
        action = action_data.get("action")

        if not selector or not action:
            return False

        try:
            if action == "click":
                await self.page.click(selector)
            elif action == "type":
                text = action_data.get("text", "")
                await self.page.fill(selector, text)
            elif action == "hover":
                await self.page.hover(selector)
            elif action == "scroll":
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            return True
        except Exception:
            return False

    async def observe(self) -> list[dict[str, str]]:
        """
        Discover what actions are available on the current page.
        Returns a list of possible actions with selectors.
        """
        html = await self._get_page_html()
        soup = BeautifulSoup(html[:30_000], "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()

        prompt = f"""Analyze this web page and list all interactive elements (buttons, links, inputs, forms).
For each, provide:
- description: what it does
- selector: CSS selector to target it
- action: "click" | "type" | "select"

Respond with a JSON array of objects.

Page HTML:
{str(soup)[:20_000]}"""

        response = await self._call_claude(prompt, "You are a web scraping assistant. Respond only with a JSON array.")
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            return json.loads(clean.strip())
        except json.JSONDecodeError:
            return []

    async def _get_page_html(self) -> str:
        if self.page is not None:
            # Playwright page
            if hasattr(self.page, "content"):
                return await self.page.content()
        if self.response:
            if isinstance(self.response, dict):
                return self.response.get("body", "")
        return ""

    async def _call_claude(self, prompt: str, system: str) -> str:
        """Call Claude API for extraction/action decisions."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",  # stable, supported indefinitely
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 2048,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]


class AICrawler(PlaywrightCrawler):
    """
    AI-powered crawler using Claude for data extraction and page interaction.
    Equivalent to Crawlee's StagehandCrawler.

    Works with both HTTP and browser mode:
    - With use_browser=False: fetches HTML via HTTP, Claude reads the HTML
    - With use_browser=True:  full Playwright browser, Claude controls it

    Args:
        api_key: Anthropic API key
        model: Claude model to use (default: claude-haiku-4-5 for speed/cost)
        use_browser: Use real browser (default True for JS-heavy sites)

    Example:
        crawler = AICrawler(api_key="sk-ant-...", model="claude-haiku-4-5-20251001")

        @router.default_handler
        async def handler(ctx):
            product = await ctx.extract("product name, price, rating, and availability")
            await dataset.push_data(product)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
        use_browser: bool = True,
        **kwargs,
    ) -> None:
        import os
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError("Anthropic API key required: pass api_key= or set ANTHROPIC_API_KEY env var")
        if use_browser:
            super().__init__(**kwargs)
        else:
            # HTTP mode — skip browser init, use CheerioCrawler parent
            from .cheerio_crawler import CheerioCrawler
            # Bypass PlaywrightCrawler.__init__ and go up to BaseCrawler
            from .base_crawler import BaseCrawler
            BaseCrawler.__init__(self, **kwargs)
            self._browser_type = "chromium"
            self._headless = True
            self._launch_options = {}
            self._wait_until = "networkidle"
            self._inject_fingerprint = False
            self._stealth_mode = False
            self._random_interactions = False
            self._browser = None
            self._playwright = None

        self._api_key = resolved_key
        self._model = model
        self._use_browser = use_browser

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        if self._use_browser:
            base_ctx = await super()._fetch_and_build_context(request, session, proxy_info)
        else:
            from .cheerio_crawler import CheerioCrawler
            base_ctx = await CheerioCrawler._fetch_and_build_context(
                self, request, session, proxy_info
            )

        # Wrap in AICrawlingContext with Claude capabilities
        return AICrawlingContext(
            request=base_ctx.request,
            response=base_ctx.response,
            parsed=base_ctx.parsed,
            page=base_ctx.page,
            crawler=self,
            session=base_ctx.session,
            proxy_info=base_ctx.proxy_info,
            log=base_ctx.log,
            api_key=self._api_key,
            model=self._model,
        )
