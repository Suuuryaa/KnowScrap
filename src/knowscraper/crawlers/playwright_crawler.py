"""
KnowScraper - PlaywrightCrawler
Full browser automation crawler using Playwright.
Injects browser fingerprints from Node.js service.
Handles JavaScript-heavy sites, SPAs, and dynamic content.
"""

from __future__ import annotations

from typing import Any

from ..anti_detection.bridge import get_bridge
from ..anti_detection.stealth import apply_stealth, random_viewport_interaction
from ..core.configuration import Configuration
from ..core.request import Request
from ..core.router import CrawlingContext
from .base_crawler import BaseCrawler


class PlaywrightCrawler(BaseCrawler):
    """
    Full browser crawler powered by Playwright.
    - Injects real browser fingerprints (canvas, WebGL, fonts, screen)
    - Supports proxy per browser context
    - Supports stealth mode to evade bot detection
    - context.page gives you the Playwright Page object
    """

    def __init__(
        self,
        *,
        browser_type: str | None = None,
        headless: bool | None = None,
        launch_options: dict | None = None,
        wait_until: str = "networkidle",  # "load", "domcontentloaded", "networkidle"
        inject_fingerprint: bool = True,
        stealth_mode: bool = True,         # JS patches + human-like interactions
        random_interactions: bool = False,  # random mouse/scroll after page load
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._browser_type = browser_type or self._config.browser_type
        self._headless = headless if headless is not None else self._config.headless
        self._launch_options = launch_options or {}
        self._wait_until = wait_until
        self._inject_fingerprint = inject_fingerprint
        self._stealth_mode = stealth_mode
        self._random_interactions = random_interactions
        self._browser = None
        self._playwright = None

    async def _setup(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright_ctx = async_playwright()
        self._playwright = await self._playwright_ctx.start()

        browser_launcher = getattr(self._playwright, self._browser_type)
        self._browser = await browser_launcher.launch(
            headless=self._headless,
            **self._launch_options,
        )
        self._log.info(
            f"Browser started: {self._browser_type} (headless={self._headless})"
        )

        # Start anti-detection service if enabled
        if self._use_anti_detection and self._config.node_service_enabled:
            bridge = get_bridge(self._config.node_service_url)
            try:
                await bridge.start()
                self._log.info("Anti-detection service started")
            except Exception as e:
                self._log.warning(f"Anti-detection service unavailable: {e}")
                self._use_anti_detection = False

    async def _fetch_and_build_context(
        self, request: Request, session: Any, proxy_info: Any
    ) -> CrawlingContext:
        fingerprint_data = None
        extra_headers = {}

        if self._inject_fingerprint and self._use_anti_detection:
            try:
                bridge = get_bridge(self._config.node_service_url)
                fingerprint_data = await bridge.get_fingerprint(
                    browser=self._browser_type if self._browser_type != "chromium" else "chrome"
                )
                extra_headers = fingerprint_data.get("headers", {})
            except Exception as e:
                self._log.warning(f"Fingerprint generation failed: {e}")

        # Build context options
        context_options: dict = {}
        if proxy_info:
            context_options["proxy"] = proxy_info.to_playwright()
        if session.cookies:
            pass  # cookies set after context creation

        # Apply fingerprint to viewport/device
        if fingerprint_data:
            fp = fingerprint_data.get("fingerprint", {})
            screen = fp.get("screen", {})
            if screen:
                context_options["viewport"] = {
                    "width": screen.get("width", 1920),
                    "height": screen.get("height", 1080),
                }

        browser_context = await self._browser.new_context(**context_options)

        # Set cookies from session
        if session.cookies:
            await browser_context.add_cookies([
                {"name": k, "value": v, "url": request.url}
                for k, v in session.cookies.items()
            ])

        # Set extra headers (from fingerprint)
        if extra_headers:
            await browser_context.set_extra_http_headers({
                **extra_headers,
                **request.headers,
            })

        # Inject fingerprint scripts if available
        if fingerprint_data:
            await self._inject_fingerprint_scripts(browser_context, fingerprint_data)

        page = await browser_context.new_page()

        # Apply stealth patches before any navigation
        if self._stealth_mode:
            await apply_stealth(page)

        try:
            await page.goto(request.url, wait_until=self._wait_until, timeout=self._timeout * 1000)

            # Optional human-like interactions after page loads
            if self._random_interactions:
                await random_viewport_interaction(page)

            # Save any new cookies back to session
            cookies = await browser_context.cookies()
            for cookie in cookies:
                session.cookies[cookie["name"]] = cookie["value"]

            return CrawlingContext(
                request=request,
                page=page,
                crawler=self,
                session=session,
                proxy_info=proxy_info,
                log=self._log,
            )
        except Exception:
            await browser_context.close()
            raise

    async def _inject_fingerprint_scripts(self, context, fingerprint_data: dict) -> None:
        """Inject fingerprint override scripts into the browser context."""
        fp = fingerprint_data.get("fingerprint", {})

        # Override navigator properties
        nav = fp.get("navigator", {})
        if nav:
            script = f"""
                Object.defineProperty(navigator, 'platform', {{get: () => {repr(nav.get('platform', 'Win32'))}}});
                Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {nav.get('hardwareConcurrency', 8)}}});
                Object.defineProperty(navigator, 'deviceMemory', {{get: () => {nav.get('deviceMemory', 8)}}});
            """
            await context.add_init_script(script)

        # Override WebGL renderer
        webgl = fp.get("videoCard", {})
        if webgl:
            renderer = webgl.get("renderer", "")
            vendor = webgl.get("vendor", "")
            if renderer or vendor:
                script = f"""
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(param) {{
                        if (param === 37446) return {repr(renderer)};
                        if (param === 37445) return {repr(vendor)};
                        return getParameter.call(this, param);
                    }};
                """
                await context.add_init_script(script)

    async def _teardown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        if self._use_anti_detection:
            bridge = get_bridge(self._config.node_service_url)
            await bridge.stop()
        await super()._teardown()
