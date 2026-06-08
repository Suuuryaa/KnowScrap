"""
KnowScraper - Dataset
Stores scraped results. Supports JSON lines and CSV export.
"""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any, AsyncIterator


class Dataset:
    def __init__(self, name: str = "default", storage_dir: str = ".knowscraper/datasets") -> None:
        self._name = name
        self._dir = Path(storage_dir) / name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "data.jsonl"
        self._lock = asyncio.Lock()
        self._count = self._count_existing()

    def _count_existing(self) -> int:
        if not self._file.exists():
            return 0
        with open(self._file) as f:
            return sum(1 for _ in f)

    async def push_data(self, data: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Append one or more records to the dataset."""
        items = data if isinstance(data, list) else [data]
        async with self._lock:
            with open(self._file, "a", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    self._count += 1

    async def get_data(self, offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        """Read records from the dataset with optional pagination."""
        results = []
        if not self._file.exists():
            return results
        with open(self._file, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < offset:
                    continue
                if limit is not None and len(results) >= limit:
                    break
                results.append(json.loads(line))
        return results

    async def iterate(self) -> AsyncIterator[dict[str, Any]]:
        """Stream records one by one — memory efficient for large datasets."""
        if not self._file.exists():
            return
        with open(self._file, encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

    async def export_to_csv(self, path: str | None = None) -> Path:
        """Export dataset to CSV. Returns the output path."""
        out = Path(path) if path else self._dir / "data.csv"
        records = await self.get_data()
        if not records:
            out.touch()
            return out
        fieldnames = list(records[0].keys())
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return out

    async def export_to_json(self, path: str | None = None) -> Path:
        """Export dataset as a proper JSON array."""
        out = Path(path) if path else self._dir / "data.json"
        records = await self.get_data()
        with open(out, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return out

    @property
    def count(self) -> int:
        return self._count

    async def drop(self) -> None:
        """Clear all data."""
        async with self._lock:
            if self._file.exists():
                self._file.unlink()
            self._count = 0

    def __repr__(self) -> str:
        return f"Dataset(name={self._name!r}, count={self._count})"
