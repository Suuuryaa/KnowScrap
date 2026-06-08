"""
KnowScraper - RequestQueue
SQLite-backed persistent queue with deduplication.
Survives crashes — resumes where it left off.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import AsyncIterator

from .request import Request, RequestState


class RequestQueue:
    def __init__(self, db_path: str = ".knowscraper/queue.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._create_table()
        return self._conn

    def _create_table(self) -> None:
        self._get_conn().execute("""
            CREATE TABLE IF NOT EXISTS requests (
                unique_key TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                label TEXT,
                method TEXT DEFAULT 'GET',
                headers TEXT DEFAULT '{}',
                payload TEXT,
                user_data TEXT DEFAULT '{}',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                state TEXT DEFAULT 'PENDING',
                created_at REAL
            )
        """)
        self._get_conn().commit()

    async def add_request(self, request: Request) -> bool:
        """Add a request. Returns True if added, False if duplicate."""
        async with self._lock:
            import json
            conn = self._get_conn()
            try:
                conn.execute("""
                    INSERT INTO requests
                    (unique_key, url, label, method, headers, payload, user_data,
                     retry_count, max_retries, state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request.unique_key,
                    request.url,
                    request.label,
                    request.method,
                    json.dumps(request.headers),
                    json.dumps(request.payload) if request.payload else None,
                    json.dumps(request.user_data),
                    request.retry_count,
                    request.max_retries,
                    request.state.value,
                    request.created_at,
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate

    async def add_requests(self, requests: list[Request]) -> int:
        """Bulk add. Returns count of newly added (non-duplicate) requests."""
        added = 0
        for req in requests:
            if await self.add_request(req):
                added += 1
        return added

    async def fetch_next(self) -> Request | None:
        """Fetch next PENDING request and mark it IN_PROGRESS."""
        async with self._lock:
            import json
            conn = self._get_conn()
            row = conn.execute("""
                SELECT * FROM requests
                WHERE state = 'PENDING'
                ORDER BY created_at ASC
                LIMIT 1
            """).fetchone()

            if row is None:
                return None

            conn.execute("""
                UPDATE requests SET state = 'IN_PROGRESS' WHERE unique_key = ?
            """, (row["unique_key"],))
            conn.commit()

            return Request(
                url=row["url"],
                label=row["label"],
                method=row["method"],
                headers=json.loads(row["headers"]),
                payload=json.loads(row["payload"]) if row["payload"] else None,
                user_data=json.loads(row["user_data"]),
                retry_count=row["retry_count"],
                max_retries=row["max_retries"],
                state=RequestState.IN_PROGRESS,
                created_at=row["created_at"],
                unique_key=row["unique_key"],
            )

    async def mark_done(self, request: Request) -> None:
        async with self._lock:
            self._get_conn().execute(
                "UPDATE requests SET state = 'DONE' WHERE unique_key = ?",
                (request.unique_key,)
            )
            self._get_conn().commit()

    async def mark_failed(self, request: Request) -> None:
        async with self._lock:
            request.mark_failed()
            self._get_conn().execute("""
                UPDATE requests SET state = ?, retry_count = ? WHERE unique_key = ?
            """, (request.state.value, request.retry_count, request.unique_key))
            self._get_conn().commit()

    async def is_empty(self) -> bool:
        conn = self._get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE state IN ('PENDING', 'IN_PROGRESS')"
        ).fetchone()[0]
        return count == 0

    async def get_stats(self) -> dict[str, int]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT state, COUNT(*) as cnt FROM requests GROUP BY state"
        ).fetchall()
        return {row["state"]: row["cnt"] for row in rows}

    async def __aiter__(self) -> AsyncIterator[Request]:
        while True:
            req = await self.fetch_next()
            if req is None:
                break
            yield req

    async def purge(self) -> None:
        """Delete all requests — used for a fresh crawl start."""
        async with self._lock:
            self._get_conn().execute("DELETE FROM requests")
            self._get_conn().commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
