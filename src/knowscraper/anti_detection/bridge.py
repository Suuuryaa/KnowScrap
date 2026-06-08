"""
KnowScraper - Anti-Detection Bridge
Python interface to the Node.js anti-detection microservice.
Handles service lifecycle (start/stop) and all API calls.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


NODE_SERVICE_DIR = Path(__file__).parent / "node_service"
DEFAULT_URL = "http://127.0.0.1:9119"


class AntiDetectionBridge:
    def __init__(self, service_url: str = DEFAULT_URL) -> None:
        self._url = service_url.rstrip("/")
        self._process: subprocess.Popen | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Start the Node.js service if not already running."""
        if await self._is_running():
            return

        # Install dependencies if needed
        if not (NODE_SERVICE_DIR / "node_modules").exists():
            await self._install_deps()

        self._process = subprocess.Popen(
            ["node", "server.js"],
            cwd=NODE_SERVICE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for service to be ready
        for _ in range(20):
            await asyncio.sleep(0.5)
            if await self._is_running():
                return

        raise RuntimeError("Anti-detection service failed to start")

    async def stop(self) -> None:
        if self._process:
            self._process.terminate()
            self._process = None
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _is_running(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._url}/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def _install_deps(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "npm", "install",
            cwd=NODE_SERVICE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        payload: Any = None,
        proxy: str | None = None,
        session_token: str | None = None,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Make an HTTP request via Node.js got-scraping (real TLS fingerprint).
        Returns dict with: status, headers, body, url
        """
        body: dict[str, Any] = {
            "url": url,
            "method": method,
            "headers": headers or {},
            "timeout": timeout,
        }
        if payload:
            body["payload"] = payload
        if proxy:
            body["proxy"] = proxy
        if session_token:
            body["session_token"] = session_token

        resp = await self._get_client().post(f"{self._url}/fetch", json=body)
        resp.raise_for_status()
        return resp.json()

    async def get_headers(
        self,
        *,
        browser: str | None = None,
        os: str | None = None,
        device: str | None = None,
        locale: str | None = None,
    ) -> dict[str, str]:
        """Generate realistic browser-consistent headers."""
        body = {}
        if browser:
            body["browser"] = browser
        if os:
            body["os"] = os
        if device:
            body["device"] = device
        if locale:
            body["locale"] = locale

        resp = await self._get_client().post(f"{self._url}/headers", json=body)
        resp.raise_for_status()
        return resp.json()["headers"]

    async def get_fingerprint(
        self,
        *,
        browser: str | None = None,
        os: str | None = None,
        device: str | None = None,
    ) -> dict[str, Any]:
        """Generate a full browser fingerprint + headers for Playwright injection."""
        body = {}
        if browser:
            body["browser"] = browser
        if os:
            body["os"] = os
        if device:
            body["device"] = device

        resp = await self._get_client().post(f"{self._url}/fingerprint", json=body)
        resp.raise_for_status()
        return resp.json()


# Global bridge instance
_bridge: AntiDetectionBridge | None = None


def get_bridge(service_url: str = DEFAULT_URL) -> AntiDetectionBridge:
    global _bridge
    if _bridge is None:
        _bridge = AntiDetectionBridge(service_url)
    return _bridge
