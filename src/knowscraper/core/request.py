"""
KnowScraper - Request
Represents a single URL to be crawled, with metadata, retry state, and labels.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestState(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class Request:
    url: str
    label: str | None = None
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] | str | None = None
    user_data: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    state: RequestState = RequestState.PENDING
    created_at: float = field(default_factory=time.time)
    unique_key: str = field(default="")

    def __post_init__(self) -> None:
        if not self.unique_key:
            self.unique_key = self._compute_key()

    def _compute_key(self) -> str:
        raw = f"{self.method}:{self.url}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def mark_failed(self) -> None:
        self.retry_count += 1
        self.state = RequestState.FAILED if not self.can_retry else RequestState.PENDING

    def mark_done(self) -> None:
        self.state = RequestState.DONE

    def mark_in_progress(self) -> None:
        self.state = RequestState.IN_PROGRESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "label": self.label,
            "method": self.method,
            "headers": self.headers,
            "payload": self.payload,
            "user_data": self.user_data,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "state": self.state.value,
            "created_at": self.created_at,
            "unique_key": self.unique_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Request":
        data = data.copy()
        data["state"] = RequestState(data.get("state", "PENDING"))
        return cls(**data)

    def __repr__(self) -> str:
        return f"Request(url={self.url!r}, label={self.label!r}, retry={self.retry_count})"
