"""
KnowScraper - AutoscaledPool
Dynamically adjusts concurrency based on CPU and memory usage.
Mirrors Crawlee's AutoscaledPool behavior.
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Callable, Awaitable

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class AutoscaledPool:
    def __init__(
        self,
        *,
        min_concurrency: int = 1,
        max_concurrency: int = 10,
        desired_concurrency: int | None = None,
        scale_up_step_ratio: float = 0.05,    # grow by 5% each tick
        scale_down_step_ratio: float = 0.05,  # shrink by 5% each tick
        max_cpu_percent: float = 75.0,
        max_memory_percent: float = 80.0,
        scale_interval: float = 5.0,          # seconds between scale checks
    ) -> None:
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.current_concurrency = desired_concurrency or min(4, max_concurrency)
        self._scale_up_step = scale_up_step_ratio
        self._scale_down_step = scale_down_step_ratio
        self._max_cpu = max_cpu_percent
        self._max_memory = max_memory_percent
        self._scale_interval = scale_interval
        self._semaphore = asyncio.Semaphore(self.current_concurrency)
        self._running = 0
        self._lock = asyncio.Lock()

    def _system_load(self) -> tuple[float, float]:
        """Returns (cpu_percent, memory_percent)."""
        if not PSUTIL_AVAILABLE:
            return 0.0, 0.0
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        return cpu, mem

    async def _autoscale_loop(self) -> None:
        while True:
            await asyncio.sleep(self._scale_interval)
            cpu, mem = self._system_load()

            async with self._lock:
                if cpu > self._max_cpu or mem > self._max_memory:
                    # System under pressure — scale down
                    step = max(1, int(self.current_concurrency * self._scale_down_step))
                    new = max(self.min_concurrency, self.current_concurrency - step)
                else:
                    # System healthy — scale up
                    step = max(1, int(self.current_concurrency * self._scale_up_step))
                    new = min(self.max_concurrency, self.current_concurrency + step)

                if new != self.current_concurrency:
                    self.current_concurrency = new
                    self._semaphore = asyncio.Semaphore(new)

    async def run(
        self,
        task_fn: Callable[[], Awaitable[None]],
        source: AsyncIterator,
    ) -> None:
        """
        Pull items from `source`, run `task_fn` on each with
        dynamic concurrency control.
        """
        scaler = asyncio.create_task(self._autoscale_loop())
        tasks: set[asyncio.Task] = set()

        try:
            async for item in source:
                await self._semaphore.acquire()

                async def _run(i=item):
                    try:
                        await task_fn(i)
                    finally:
                        self._semaphore.release()

                t = asyncio.create_task(_run())
                tasks.add(t)
                t.add_done_callback(tasks.discard)

            # Wait for all remaining tasks
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            scaler.cancel()

    @property
    def stats(self) -> dict:
        cpu, mem = self._system_load()
        return {
            "current_concurrency": self.current_concurrency,
            "min_concurrency": self.min_concurrency,
            "max_concurrency": self.max_concurrency,
            "cpu_percent": cpu,
            "memory_percent": mem,
        }
