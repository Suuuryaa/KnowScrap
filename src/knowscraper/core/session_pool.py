"""
KnowScraper - SessionPool
Manages a pool of fake "user" sessions — each with its own cookies,
headers, and proxy. Retires blocked sessions and creates new ones.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any


BLOCKED_STATUS_CODES = {401, 403, 407, 429, 503}


@dataclass
class Session:
    id: str
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    use_count: int = 0
    max_uses: int = 50
    error_count: int = 0
    max_errors: int = 3
    created_at: float = field(default_factory=time.time)
    retired: bool = False

    @property
    def is_usable(self) -> bool:
        return not self.retired and self.use_count < self.max_uses and self.error_count < self.max_errors

    def record_use(self) -> None:
        self.use_count += 1

    def record_error(self) -> None:
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.retire()

    def retire(self) -> None:
        self.retired = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cookies": self.cookies,
            "headers": self.headers,
            "proxy": self.proxy,
            "use_count": self.use_count,
        }


class SessionPool:
    def __init__(
        self,
        max_pool_size: int = 20,
        max_session_uses: int = 50,
        max_session_errors: int = 3,
    ) -> None:
        self._max_pool_size = max_pool_size
        self._max_session_uses = max_session_uses
        self._max_session_errors = max_session_errors
        self._sessions: list[Session] = []
        self._lock = asyncio.Lock()
        self._counter = 0

    def _create_session(self, proxy: str | None = None) -> Session:
        self._counter += 1
        return Session(
            id=f"session_{self._counter}_{int(time.time())}",
            max_uses=self._max_session_uses,
            max_errors=self._max_session_errors,
            proxy=proxy,
        )

    async def get_session(self, proxy: str | None = None) -> Session:
        async with self._lock:
            usable = [s for s in self._sessions if s.is_usable]

            if usable:
                session = random.choice(usable)
                session.record_use()
                return session

            # Create new session if pool not full
            if len(self._sessions) < self._max_pool_size:
                session = self._create_session(proxy=proxy)
                session.record_use()
                self._sessions.append(session)
                return session

            # Pool full — retire oldest and create fresh
            self._sessions = [s for s in self._sessions if not s.retired]
            session = self._create_session(proxy=proxy)
            session.record_use()
            self._sessions.append(session)
            return session

    async def retire_session(self, session: Session) -> None:
        async with self._lock:
            session.retire()

    def mark_session_blocked(self, session: Session, status_code: int) -> bool:
        """Returns True if session was retired due to block."""
        if status_code in BLOCKED_STATUS_CODES:
            session.record_error()
            if not session.is_usable:
                session.retire()
                return True
        return False

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total": len(self._sessions),
            "usable": sum(1 for s in self._sessions if s.is_usable),
            "retired": sum(1 for s in self._sessions if s.retired),
        }
