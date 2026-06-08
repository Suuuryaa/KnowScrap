"""
KnowScraper - ProxyConfiguration
Manages proxy rotation. Supports plain proxies, authenticated proxies,
and proxy lists with round-robin or random rotation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ProxyInfo:
    url: str
    hostname: str
    port: int
    username: str | None = None
    password: str | None = None
    protocol: str = "http"

    @classmethod
    def from_url(cls, url: str) -> "ProxyInfo":
        parsed = urlparse(url)
        return cls(
            url=url,
            hostname=parsed.hostname or "",
            port=parsed.port or 8080,
            username=parsed.username,
            password=parsed.password,
            protocol=parsed.scheme or "http",
        )

    def to_httpx(self) -> dict[str, str]:
        return {"http://": self.url, "https://": self.url}

    def to_playwright(self) -> dict:
        result: dict = {"server": f"{self.protocol}://{self.hostname}:{self.port}"}
        if self.username:
            result["username"] = self.username
        if self.password:
            result["password"] = self.password
        return result


class ProxyConfiguration:
    def __init__(
        self,
        proxy_urls: list[str] | None = None,
        rotate: str = "random",  # "random" or "round_robin"
    ) -> None:
        self._proxies = [ProxyInfo.from_url(u) for u in (proxy_urls or [])]
        self._rotate = rotate
        self._index = 0

    def new_proxy_info(self) -> ProxyInfo | None:
        if not self._proxies:
            return None
        if self._rotate == "round_robin":
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy
        return random.choice(self._proxies)

    @property
    def is_configured(self) -> bool:
        return bool(self._proxies)

    def __repr__(self) -> str:
        return f"ProxyConfiguration(proxies={len(self._proxies)}, rotate={self._rotate!r})"
