"""KnowScraper - Logging via loguru."""

from __future__ import annotations

import sys

try:
    from loguru import logger as _loguru_logger

    def get_logger(name: str):
        return _loguru_logger.bind(crawler=name)

except ImportError:
    import logging

    def get_logger(name: str):
        log = logging.getLogger(f"knowscraper.{name}")
        if not log.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
            log.addHandler(handler)
            log.setLevel(logging.INFO)
        return log
