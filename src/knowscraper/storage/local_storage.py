"""
KnowScraper - LocalStorage
Filesystem-backed storage client.
Datasets saved as JSONL files. RequestQueue backed by SQLite.
Compatible with the same interface as MemoryStorage for easy swapping.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class LocalStorage:
    """
    Filesystem storage backend.
    All data persists to disk at `base_dir`.

    Directory layout:
        base_dir/
            datasets/
                <name>/
                    data.jsonl
                    data.csv      (after export)
                    data.json     (after export)
            queues/
                <name>.db         (SQLite)
            key_value_stores/
                <name>/
                    <key>.json
    """

    def __init__(self, base_dir: str = ".knowscraper") -> None:
        self.base_dir = Path(base_dir)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for sub in ("datasets", "queues", "key_value_stores"):
            (self.base_dir / sub).mkdir(parents=True, exist_ok=True)

    # ── Key-Value Store ──────────────────────────────────────────────────────

    def set_value(self, store: str, key: str, value: Any) -> None:
        store_dir = self.base_dir / "key_value_stores" / store
        store_dir.mkdir(parents=True, exist_ok=True)
        path = store_dir / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_value(self, store: str, key: str, default: Any = None) -> Any:
        path = self.base_dir / "key_value_stores" / store / f"{key}.json"
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_value(self, store: str, key: str) -> None:
        path = self.base_dir / "key_value_stores" / store / f"{key}.json"
        if path.exists():
            path.unlink()

    def list_keys(self, store: str) -> list[str]:
        store_dir = self.base_dir / "key_value_stores" / store
        if not store_dir.exists():
            return []
        return [p.stem for p in store_dir.glob("*.json")]

    # ── Dataset helpers ───────────────────────────────────────────────────────

    def dataset_path(self, name: str = "default") -> Path:
        path = self.base_dir / "datasets" / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Queue helpers ─────────────────────────────────────────────────────────

    def queue_db_path(self, name: str = "default") -> Path:
        return self.base_dir / "queues" / f"{name}.db"

    # ── Inspect ───────────────────────────────────────────────────────────────

    def list_datasets(self) -> list[str]:
        d = self.base_dir / "datasets"
        return [p.name for p in d.iterdir() if p.is_dir()] if d.exists() else []

    def dataset_size(self, name: str) -> int:
        path = self.base_dir / "datasets" / name / "data.jsonl"
        if not path.exists():
            return 0
        with open(path) as f:
            return sum(1 for _ in f)

    def purge_dataset(self, name: str) -> None:
        path = self.base_dir / "datasets" / name / "data.jsonl"
        if path.exists():
            path.unlink()

    def purge_queue(self, name: str) -> None:
        db = self.queue_db_path(name)
        if db.exists():
            db.unlink()

    def purge_all(self) -> None:
        import shutil
        shutil.rmtree(self.base_dir, ignore_errors=True)
        self._ensure_dirs()

    def __repr__(self) -> str:
        return f"LocalStorage(base_dir={self.base_dir!r})"
