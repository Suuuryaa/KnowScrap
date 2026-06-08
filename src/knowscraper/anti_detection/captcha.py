"""
KnowScraper - CAPTCHA Handler
Detects CAPTCHAs and solves them via third-party services.
Supports: 2captcha, CapSolver, AntiCaptcha.
Works with both HTTP crawlers (inject token) and Playwright crawlers (click/submit).
"""

from __future__ import annotations

import asyncio
import re
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from playwright.async_api import Page


class CaptchaType(Enum):
    RECAPTCHA_V2   = "recaptcha_v2"
    RECAPTCHA_V3   = "recaptcha_v3"
    HCAPTCHA       = "hcaptcha"
    CLOUDFLARE     = "cloudflare_turnstile"
    IMAGE_CAPTCHA  = "image"
    UNKNOWN        = "unknown"


class CaptchaNotSolvedError(Exception):
    pass


# ── Detection ─────────────────────────────────────────────────────────────────

CAPTCHA_SIGNALS = {
    CaptchaType.RECAPTCHA_V2:  [
        r"google\.com/recaptcha",
        r"grecaptcha\.execute",
        r"g-recaptcha",
    ],
    CaptchaType.RECAPTCHA_V3:  [
        r"grecaptcha\.execute\(",
        r"recaptcha/api\.js\?render=",
    ],
    CaptchaType.HCAPTCHA:  [
        r"hcaptcha\.com",
        r"h-captcha",
        r"data-hcaptcha-sitekey",
    ],
    CaptchaType.CLOUDFLARE: [
        r"challenges\.cloudflare\.com",
        r"cf-turnstile",
        r"Cloudflare Ray ID",
        r"cf_chl_",
    ],
}


def detect_captcha(html: str) -> CaptchaType:
    """Detect CAPTCHA type from HTML content."""
    for captcha_type, patterns in CAPTCHA_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, html, re.IGNORECASE):
                return captcha_type
    return CaptchaType.UNKNOWN


def extract_site_key(html: str, captcha_type: CaptchaType) -> str | None:
    """Extract the CAPTCHA site key from page HTML."""
    patterns = {
        CaptchaType.RECAPTCHA_V2: [
            r'data-sitekey=["\']([^"\']+)["\']',
            r'grecaptcha\.render\([^,]+,\s*\{[^}]*["\']sitekey["\']\s*:\s*["\']([^"\']+)["\']',
        ],
        CaptchaType.RECAPTCHA_V3: [
            r'recaptcha/api\.js\?render=([a-zA-Z0-9_-]+)',
            r'grecaptcha\.execute\(["\']([^"\']+)["\']',
        ],
        CaptchaType.HCAPTCHA: [
            r'data-sitekey=["\']([^"\']+)["\']',
            r'hcaptcha\.execute\(["\']([^"\']+)["\']',
        ],
        CaptchaType.CLOUDFLARE: [
            r'data-sitekey=["\']([^"\']+)["\']',
        ],
    }

    for pattern in patterns.get(captcha_type, []):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


# ── Solvers ───────────────────────────────────────────────────────────────────

class TwoCaptchaSolver:
    """Solve CAPTCHAs using 2captcha.com API."""

    BASE_URL = "https://2captcha.com"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        """Returns the g-recaptcha-response token."""
        task_id = await self._submit({
            "method":   "userrecaptcha",
            "googlekey": site_key,
            "pageurl":  page_url,
        })
        return await self._poll(task_id)

    async def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "verify", min_score: float = 0.5
    ) -> str:
        task_id = await self._submit({
            "method":   "userrecaptcha",
            "version":  "v3",
            "googlekey": site_key,
            "pageurl":  page_url,
            "action":   action,
            "min_score": min_score,
        })
        return await self._poll(task_id)

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        task_id = await self._submit({
            "method":  "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
        })
        return await self._poll(task_id)

    async def solve_image(self, image_base64: str) -> str:
        """Solve a simple image CAPTCHA."""
        task_id = await self._submit({
            "method": "base64",
            "body":   image_base64,
        })
        return await self._poll(task_id)

    async def _submit(self, params: dict) -> str:
        params["key"] = self._api_key
        params["json"] = 1
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.BASE_URL}/in.php", data=params)
            data = resp.json()
            if data.get("status") != 1:
                raise CaptchaNotSolvedError(f"Submit failed: {data.get('request')}")
            return str(data["request"])

    async def _poll(self, task_id: str, max_wait: int = 120) -> str:
        """Poll until solved or timeout."""
        async with httpx.AsyncClient(timeout=30) as client:
            start = time.time()
            await asyncio.sleep(15)  # Initial wait — 2captcha takes ~15s minimum
            while time.time() - start < max_wait:
                resp = await client.get(f"{self.BASE_URL}/res.php", params={
                    "key":    self._api_key,
                    "action": "get",
                    "id":     task_id,
                    "json":   1,
                })
                data = resp.json()
                if data.get("status") == 1:
                    return str(data["request"])
                if data.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                    raise CaptchaNotSolvedError("Captcha marked unsolvable")
                await asyncio.sleep(5)

        raise CaptchaNotSolvedError(f"Timeout after {max_wait}s")


class CapSolverSolver:
    """Solve CAPTCHAs using capsolver.com API."""

    BASE_URL = "https://api.capsolver.com"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        return await self._solve({
            "type":       "ReCaptchaV2TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        })

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        return await self._solve({
            "type":       "HCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        })

    async def solve_cloudflare_turnstile(self, site_key: str, page_url: str) -> str:
        return await self._solve({
            "type":       "AntiTurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": site_key,
        })

    async def _solve(self, task: dict) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            # Create task
            resp = await client.post(f"{self.BASE_URL}/createTask", json={
                "clientKey": self._api_key,
                "task":      task,
            })
            data = resp.json()
            if data.get("errorId"):
                raise CaptchaNotSolvedError(f"CapSolver error: {data.get('errorDescription')}")
            task_id = data["taskId"]

            # Poll for result
            for _ in range(24):  # 2 minute max
                await asyncio.sleep(5)
                resp = await client.post(f"{self.BASE_URL}/getTaskResult", json={
                    "clientKey": self._api_key,
                    "taskId":    task_id,
                })
                result = resp.json()
                if result.get("status") == "ready":
                    sol = result.get("solution", {})
                    return sol.get("gRecaptchaResponse") or sol.get("token") or ""
                if result.get("errorId"):
                    raise CaptchaNotSolvedError(result.get("errorDescription"))

        raise CaptchaNotSolvedError("CapSolver timeout")


# ── High-level handler ────────────────────────────────────────────────────────

class CaptchaHandler:
    """
    High-level CAPTCHA handler.
    Detects, solves, and injects the solution into the page.

    Usage:
        handler = CaptchaHandler(api_key="...", service="2captcha")

        # In a PlaywrightCrawler handler:
        if handler.is_captcha(await ctx.page.content()):
            await handler.solve_and_inject(ctx.page)
    """

    def __init__(
        self,
        api_key: str,
        service: str = "2captcha",  # "2captcha" | "capsolver"
    ) -> None:
        self._api_key = api_key
        if service == "2captcha":
            self._solver = TwoCaptchaSolver(api_key)
        elif service == "capsolver":
            self._solver = CapSolverSolver(api_key)
        else:
            raise ValueError(f"Unknown CAPTCHA service: {service!r}")

    def is_captcha(self, html: str) -> bool:
        return detect_captcha(html) != CaptchaType.UNKNOWN

    def detect(self, html: str) -> CaptchaType:
        return detect_captcha(html)

    async def solve_and_inject(self, page: "Page") -> bool:
        """
        Detect CAPTCHA on the current page, solve it, and inject the token.
        Returns True if solved and injected, False if no CAPTCHA detected.
        """
        html = await page.content()
        captcha_type = detect_captcha(html)

        if captcha_type == CaptchaType.UNKNOWN:
            return False

        site_key = extract_site_key(html, captcha_type)
        if not site_key:
            return False

        page_url = page.url
        token = None

        if captcha_type in (CaptchaType.RECAPTCHA_V2,):
            token = await self._solver.solve_recaptcha_v2(site_key, page_url)
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            token = await self._solver.solve_recaptcha_v3(site_key, page_url)
        elif captcha_type == CaptchaType.HCAPTCHA:
            token = await self._solver.solve_hcaptcha(site_key, page_url)

        if not token:
            return False

        # Inject token into the page
        await page.evaluate(f"""
            (token) => {{
                // reCAPTCHA v2 / hCaptcha
                const el = document.getElementById('g-recaptcha-response') ||
                           document.getElementById('h-captcha-response');
                if (el) {{
                    el.value = token;
                    el.style.display = 'block';
                }}
                // Trigger callbacks
                if (window.grecaptcha && window.___grecaptcha_cfg) {{
                    const id = Object.keys(window.___grecaptcha_cfg.clients || {{}})[0];
                    if (id !== undefined) {{
                        const client = window.___grecaptcha_cfg.clients[id];
                        const callback = client?.['']['']['callback'];
                        if (typeof callback === 'function') callback(token);
                    }}
                }}
                if (window.hcaptcha) {{
                    window.hcaptcha.setResponse(token);
                }}
            }}
        """, token)

        return True

    async def solve_for_http(
        self, html: str, page_url: str
    ) -> dict[str, str]:
        """
        Solve CAPTCHA for HTTP crawlers.
        Returns a dict of form fields to inject (e.g. g-recaptcha-response).
        """
        captcha_type = detect_captcha(html)
        if captcha_type == CaptchaType.UNKNOWN:
            return {}

        site_key = extract_site_key(html, captcha_type)
        if not site_key:
            return {}

        token = None
        if captcha_type == CaptchaType.RECAPTCHA_V2:
            token = await self._solver.solve_recaptcha_v2(site_key, page_url)
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            token = await self._solver.solve_recaptcha_v3(site_key, page_url)
        elif captcha_type == CaptchaType.HCAPTCHA:
            token = await self._solver.solve_hcaptcha(site_key, page_url)

        if token:
            return {"g-recaptcha-response": token, "h-captcha-response": token}
        return {}
