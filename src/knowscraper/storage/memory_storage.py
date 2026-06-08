"""
KnowScraper - MemoryStorage
Fully in-memory storage — no SQLite, no disk writes.
Fast for testing and lightweight one-shot scrapes.
Drop-in replacement for LocalStorage.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..core.request import Request, RequestState


# ── In-Memory Request Queue ───────────────────────────────────────────────────

class MemoryRequestQueue:
    """
    Drop-in replacement for RequestQueue backed by a Python list.
    No SQLite. No disk. Disappears when process ends.
    """

    def __init__(self) -> None:
        self._requests: dict[str, Request] = {}   # unique_key → Request
        self._order: list[str] = []               # insertion order
        self._lock = asyncio.Lock()

    async def add_request(self, request: Request) -> bool:
        async with self._lock:
            if request.unique_key in self._requests:
                return False
            self._requests[request.unique_key] = request
            self._order.append(request.unique_key)
            return True

    async def add_requests(self, requests: list[Request]) -> int:
        added = 0
        for r in requests:
            if await self.add_request(r):
                added += 1
        return added

    async def fetch_next(self) -> Request | None:
        async with self._lock:
            for key in self._order:
                req = self._requests[key]
                if req.state == RequestState.PENDING:
                    req.mark_in_progress()
                    return req
            return None

    async def mark_done(self, request: Request) -> None:
        async with self._lock:
            request.mark_done()

    async def mark_failed(self, request: Request) -> None:
        async with self._lock:
            request.mark_failed()

    async def is_empty(self) -> bool:
        async with self._lock:
            return not any(
                r.state in (RequestState.PENDING, RequestState.IN_PROGRESS)
                for r in self._requests.values()
            )

    async def purge(self) -> None:
        async with self._lock:
            self._requests.clear()
            self._order.clear()

    async def get_stats(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self._requests.values():
            counts[r.state.value] += 1
        return dict(counts)

    def close(self) -> None:
        pass  # nothing to close

    def __repr__(self) -> str:
        return f"MemoryRequestQueue(size={len(self._requests)})"


# ── In-Memory Dataset ─────────────────────────────────────────────────────────

class MemoryDataset:
    """
    Drop-in replacement for Dataset — stores records in a Python list.
    Supports same export methods as Dataset.
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._records: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def push_data(self, data: dict[str, Any] | list[dict[str, Any]]) -> None:
        items = data if isinstance(data, list) else [data]
        async with self._lock:
            self._records.extend(items)

    async def get_data(self, offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        async with self._lock:
            sliced = self._records[offset:]
            return sliced[:limit] if limit is not None else sliced

    async def iterate(self):
        async with self._lock:
            records = list(self._records)
        for r in records:
            yield r

    async def export_to_csv(self, path: str | None = None):
        import csv
        import io
        from pathlib import Path

        records = await self.get_data()
        if not records:
            return None

        out_path = Path(path) if path else Path(f"/tmp/{self._name}.csv")
        fieldnames = list(records[0].keys())
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return out_path

    async def export_to_json(self, path: str | None = None):
        import json
        from pathlib import Path

        records = await self.get_data()
        out_path = Path(path) if path else Path(f"/tmp/{self._name}.json")
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        return out_path

    async def drop(self) -> None:
        async with self._lock:
            self._records.clear()

    @property
    def count(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"MemoryDataset(name={self._name!r}, count={self.count})"


# ── In-Memory Key-Value Store ─────────────────────────────────────────────────

class MemoryKeyValueStore:
    """Simple in-memory key-value store."""

    def __init__(self) -> None:
        self._stores: dict[str, dict[str, Any]] = defaultdict(dict)

    def set_value(self, store: str, key: str, value: Any) -> None:
        self._stores[store][key] = value

    def get_value(self, store: str, key: str, default: Any = None) -> Any:
        return self._stores[store].get(key, default)

    def delete_value(self, store: str, key: str) -> None:
        self._stores[store].pop(key, None)

    def list_keys(self, store: str) -> list[str]:
        return list(self._stores[store].keys())

    def purge_all(self) -> None:
        self._stores.clear()
