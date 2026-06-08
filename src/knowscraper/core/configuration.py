"""
KnowScraper - Configuration
Global config singleton. Overridable via env vars (KNOWSCRAPER_* prefix).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Configuration:
    # Concurrency
    max_concurrency: int = int(os.getenv("KNOWSCRAPER_MAX_CONCURRENCY", "10"))
    min_concurrency: int = int(os.getenv("KNOWSCRAPER_MIN_CONCURRENCY", "1"))

    # Requests
    request_timeout: int = int(os.getenv("KNOWSCRAPER_REQUEST_TIMEOUT", "30"))
    max_request_retries: int = int(os.getenv("KNOWSCRAPER_MAX_RETRIES", "3"))
    request_handler_timeout: int = int(os.getenv("KNOWSCRAPER_HANDLER_TIMEOUT", "60"))

    # Delays (seconds)
    min_delay: float = float(os.getenv("KNOWSCRAPER_MIN_DELAY", "0"))
    max_delay: float = float(os.getenv("KNOWSCRAPER_MAX_DELAY", "0"))

    # Storage
    storage_dir: str = os.getenv("KNOWSCRAPER_STORAGE_DIR", ".knowscraper")

    # Anti-detection Node.js service
    node_service_url: str = os.getenv("KNOWSCRAPER_NODE_SERVICE", "http://127.0.0.1:9119")
    node_service_enabled: bool = os.getenv("KNOWSCRAPER_NODE_SERVICE_ENABLED", "true").lower() == "true"

    # Browser
    headless: bool = os.getenv("KNOWSCRAPER_HEADLESS", "true").lower() == "true"
    browser_type: str = os.getenv("KNOWSCRAPER_BROWSER", "chromium")  # chromium, firefox, webkit

    # Logging
    log_level: str = os.getenv("KNOWSCRAPER_LOG_LEVEL", "INFO")

    # Session pool
    max_pool_size: int = int(os.getenv("KNOWSCRAPER_SESSION_POOL_SIZE", "20"))

    _instance: "Configuration | None" = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def get_global(cls) -> "Configuration":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_global(cls, config: "Configuration") -> None:
        cls._instance = config
