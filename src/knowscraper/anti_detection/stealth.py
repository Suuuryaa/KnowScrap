"""
KnowScraper - Playwright Stealth
Human-like browser behaviour: mouse movement, scrolling, typing delays,
page interaction timing, and JS property overrides.
Makes automated browsers nearly indistinguishable from real users.
"""

from __future__ import annotations

import asyncio
import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


# ── JS patches injected before page load ─────────────────────────────────────

STEALTH_SCRIPTS = """
// Remove webdriver flag — most basic bot detection check
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Realistic plugin list (empty plugins = headless browser)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ];
        plugins.length = 3;
        return plugins;
    }
});

// Realistic language setup
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Permissions API — real browsers return 'default' not throw
if (window.Notification) {
    const origQuery = window.Notification.requestPermission.bind(window.Notification);
    window.Notification.requestPermission = () => Promise.resolve('default');
}

// Hide automation in chrome object
if (window.chrome) {
    window.chrome.runtime = window.chrome.runtime || {};
}

// Realistic screen dimensions (override headless defaults)
Object.defineProperty(screen, 'availWidth', { get: () => screen.width });
Object.defineProperty(screen, 'availHeight', { get: () => screen.height - 40 });

// WebGL — prevent detection via renderer string check
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};
"""


async def apply_stealth(page: "Page") -> None:
    """
    Apply all stealth patches to a Playwright page.
    Call this BEFORE navigating to any URL.
    """
    await page.add_init_script(STEALTH_SCRIPTS)


# ── Human-like mouse movement ─────────────────────────────────────────────────

def _bezier_curve(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 20,
) -> list[tuple[float, float]]:
    """Generate a Bezier curve path between two points — like a real mouse."""
    # Random control points to create natural curve
    cp1 = (
        start[0] + random.uniform(-100, 100),
        start[1] + random.uniform(-50, 50),
    )
    cp2 = (
        end[0] + random.uniform(-100, 100),
        end[1] + random.uniform(-50, 50),
    )

    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (
            (1 - t) ** 3 * start[0]
            + 3 * (1 - t) ** 2 * t * cp1[0]
            + 3 * (1 - t) * t ** 2 * cp2[0]
            + t ** 3 * end[0]
        )
        y = (
            (1 - t) ** 3 * start[1]
            + 3 * (1 - t) ** 2 * t * cp1[1]
            + 3 * (1 - t) * t ** 2 * cp2[1]
            + t ** 3 * end[1]
        )
        points.append((round(x), round(y)))
    return points


async def human_mouse_move(
    page: "Page",
    target_x: float,
    target_y: float,
    steps: int = 25,
) -> None:
    """Move mouse from current position to target with natural Bezier curve."""
    # Get current mouse position (approximate from last known)
    current = await page.evaluate("() => [window._mouseX || 0, window._mouseY || 0]")
    start = (float(current[0]), float(current[1]))
    end = (float(target_x), float(target_y))

    path = _bezier_curve(start, end, steps)
    for x, y in path:
        await page.mouse.move(x, y)
        # Variable speed — faster in middle, slower at start/end
        await asyncio.sleep(random.uniform(0.005, 0.02))

    # Track position
    await page.evaluate(
        f"() => {{ window._mouseX = {target_x}; window._mouseY = {target_y}; }}"
    )


async def human_click(
    page: "Page",
    selector: str,
    move_mouse: bool = True,
) -> None:
    """Click an element with human-like mouse movement and timing."""
    element = await page.query_selector(selector)
    if not element:
        return

    box = await element.bounding_box()
    if not box:
        return

    # Aim at a random point within the element (not always dead center)
    target_x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
    target_y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)

    if move_mouse:
        await human_mouse_move(page, target_x, target_y)

    # Brief pause before clicking — humans don't click instantly
    await asyncio.sleep(random.uniform(0.05, 0.3))
    await page.mouse.click(target_x, target_y)
    await asyncio.sleep(random.uniform(0.05, 0.2))


async def human_scroll(
    page: "Page",
    direction: str = "down",
    amount: int | None = None,
    steps: int = 5,
) -> None:
    """
    Scroll the page in human-like increments.
    direction: 'down' | 'up'
    amount: pixels to scroll (random if None)
    """
    if amount is None:
        amount = random.randint(300, 800)

    sign = 1 if direction == "down" else -1
    per_step = (amount * sign) // steps

    for _ in range(steps):
        await page.evaluate(f"window.scrollBy(0, {per_step})")
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def human_type(
    page: "Page",
    selector: str,
    text: str,
    min_delay: float = 0.05,
    max_delay: float = 0.18,
    mistake_rate: float = 0.03,
) -> None:
    """
    Type text into an input field with realistic key-by-key timing.
    Occasionally makes typos and corrects them (controlled by mistake_rate).
    """
    await human_click(page, selector)
    await asyncio.sleep(random.uniform(0.1, 0.3))

    for char in text:
        # Occasional typo
        if random.random() < mistake_rate:
            wrong = random.choice("qwertyuiopasdfghjklzxcvbnm")
            await page.keyboard.type(wrong)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(min_delay, max_delay))


async def wait_human_like(
    min_seconds: float = 0.5,
    max_seconds: float = 2.5,
) -> None:
    """Random pause — simulates human reading/thinking time."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def random_viewport_interaction(page: "Page") -> None:
    """
    Do a few random mouse movements and a small scroll.
    Makes the browser session look like an active human user.
    """
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    w, h = viewport["width"], viewport["height"]

    # 2-4 random mouse moves
    for _ in range(random.randint(2, 4)):
        x = random.uniform(w * 0.1, w * 0.9)
        y = random.uniform(h * 0.1, h * 0.9)
        await human_mouse_move(page, x, y, steps=random.randint(10, 20))
        await asyncio.sleep(random.uniform(0.1, 0.5))

    # Small scroll down then up
    await human_scroll(page, "down", random.randint(100, 400))
    await asyncio.sleep(random.uniform(0.3, 0.8))
    await human_scroll(page, "up", random.randint(50, 200))
