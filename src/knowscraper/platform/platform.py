"""
KnowScraper - KnowPlatform
Deployment manifest, environment management, and Docker packaging.
Equivalent in concept to Apify Platform — provides a standardised way
to configure, deploy, and run scrapers in any environment.

Unlike Apify (proprietary SaaS), KnowPlatform targets:
  - Local runs
  - Docker containers
  - Any cloud (AWS, GCP, Azure, Fly.io, Railway, etc.)
  - GitHub Actions / CI pipelines
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunConfig:
    """
    Scraper run configuration — equivalent to Apify's Actor input schema.
    Loaded from environment, a JSON file, or passed directly in code.
    """

    start_urls: list[str] = field(default_factory=list)
    max_pages: int | None = None
    max_concurrency: int = 10
    proxy_urls: list[str] = field(default_factory=list)
    use_anti_detection: bool = True
    headless: bool = True
    output_dataset: str = "default"
    custom: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "RunConfig":
        """Load config from KNOWSCRAPER_INPUT env var (JSON string)."""
        raw = os.getenv("KNOWSCRAPER_INPUT", "{}")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        return cls(
            start_urls=data.get("startUrls", []),
            max_pages=data.get("maxPages"),
            max_concurrency=data.get("maxConcurrency", 10),
            proxy_urls=data.get("proxyUrls", []),
            use_anti_detection=data.get("useAntiDetection", True),
            headless=data.get("headless", True),
            output_dataset=data.get("outputDataset", "default"),
            custom={k: v for k, v in data.items() if k not in {
                "startUrls", "maxPages", "maxConcurrency", "proxyUrls",
                "useAntiDetection", "headless", "outputDataset"
            }},
        )

    @classmethod
    def from_file(cls, path: str) -> "RunConfig":
        """Load config from a JSON file."""
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        return cls(
            start_urls=data.get("startUrls", data.get("start_urls", [])),
            max_pages=data.get("maxPages", data.get("max_pages")),
            max_concurrency=data.get("maxConcurrency", data.get("max_concurrency", 10)),
            proxy_urls=data.get("proxyUrls", data.get("proxy_urls", [])),
            use_anti_detection=data.get("useAntiDetection", data.get("use_anti_detection", True)),
            headless=data.get("headless", True),
            output_dataset=data.get("outputDataset", data.get("output_dataset", "default")),
            custom=data.get("custom", {k: v for k, v in data.items() if k not in {
                "startUrls", "start_urls", "maxPages", "max_pages",
                "maxConcurrency", "max_concurrency", "proxyUrls", "proxy_urls",
                "useAntiDetection", "use_anti_detection", "headless",
                "outputDataset", "output_dataset", "custom",
            }}),
        )

    def to_dict(self) -> dict:
        return {
            "startUrls": self.start_urls,
            "maxPages": self.max_pages,
            "maxConcurrency": self.max_concurrency,
            "proxyUrls": self.proxy_urls,
            "useAntiDetection": self.use_anti_detection,
            "headless": self.headless,
            "outputDataset": self.output_dataset,
            "custom": self.custom,
        }


class KnowPlatform:
    """
    Platform utilities for deployment and cloud operation.

    Provides:
    - Dockerfile generation for containerised deployment
    - Docker Compose for local multi-container runs
    - GitHub Actions workflow for CI/CD
    - Environment configuration helpers
    - Cloud deployment guides

    Usage:
        platform = KnowPlatform(project_dir=".")
        platform.generate_dockerfile()
        platform.generate_github_action()
    """

    DOCKERFILE_TEMPLATE = '''FROM python:3.12-slim

# Install Node.js for anti-detection service
RUN apt-get update && apt-get install -y curl && \\
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \\
    apt-get install -y nodejs && \\
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \\
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \\
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \\
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 && \\
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

# Install Node.js anti-detection service
COPY . .
RUN cd /app/anti_detection/node_service && npm install --production

ENV KNOWSCRAPER_HEADLESS=true
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
'''

    DOCKER_COMPOSE_TEMPLATE = '''version: "3.9"
services:
  scraper:
    build: .
    environment:
      - KNOWSCRAPER_MAX_CONCURRENCY=10
      - KNOWSCRAPER_HEADLESS=true
      - KNOWSCRAPER_INPUT=\'{"startUrls": ["https://example.com"]}\'
    volumes:
      - ./output:/app/.knowscraper
    restart: unless-stopped
'''

    GITHUB_ACTION_TEMPLATE = '''name: Run KnowScraper

on:
  schedule:
    - cron: "0 9 * * *"   # daily at 9am UTC
  workflow_dispatch:        # manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium --with-deps
          cd anti_detection/node_service && npm install

      - name: Run scraper
        env:
          KNOWSCRAPER_INPUT: \'{"startUrls": ["https://example.com"]}\'
        run: python main.py

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: scrape-results
          path: .knowscraper/datasets/
'''

    def __init__(self, project_dir: str = ".") -> None:
        self._dir = Path(project_dir)

    def generate_dockerfile(self, output: str | None = None) -> Path:
        """Generate a production-ready Dockerfile."""
        path = Path(output or self._dir / "Dockerfile")
        path.write_text(self.DOCKERFILE_TEMPLATE)
        print(f"✓ Dockerfile written to {path}")
        return path

    def generate_docker_compose(self, output: str | None = None) -> Path:
        """Generate a docker-compose.yml for local deployment."""
        path = Path(output or self._dir / "docker-compose.yml")
        path.write_text(self.DOCKER_COMPOSE_TEMPLATE)
        print(f"✓ docker-compose.yml written to {path}")
        return path

    def generate_github_action(self, output: str | None = None) -> Path:
        """Generate a GitHub Actions workflow file."""
        workflow_dir = self._dir / ".github" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        path = Path(output or workflow_dir / "scraper.yml")
        path.write_text(self.GITHUB_ACTION_TEMPLATE)
        print(f"✓ GitHub Actions workflow written to {path}")
        return path

    def generate_input_schema(self, output: str | None = None) -> Path:
        """Generate an input schema JSON file documenting accepted config."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "KnowScraper Input",
            "type": "object",
            "properties": {
                "startUrls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to start scraping from",
                },
                "maxPages": {
                    "type": ["integer", "null"],
                    "description": "Maximum number of pages to scrape (null = unlimited)",
                },
                "maxConcurrency": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum concurrent requests",
                },
                "proxyUrls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of proxy URLs for rotation",
                },
                "useAntiDetection": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable TLS fingerprinting and browser fingerprints",
                },
                "headless": {
                    "type": "boolean",
                    "default": True,
                    "description": "Run browser in headless mode",
                },
            },
            "required": ["startUrls"],
        }
        path = Path(output or self._dir / "input_schema.json")
        path.write_text(json.dumps(schema, indent=2))
        print(f"✓ Input schema written to {path}")
        return path

    def build_docker(self, tag: str = "knowscraper:latest") -> None:
        """Build Docker image."""
        subprocess.run(
            ["docker", "build", "-t", tag, str(self._dir)],
            check=True,
        )
        print(f"✓ Docker image built: {tag}")

    def run_docker(
        self,
        tag: str = "knowscraper:latest",
        config: RunConfig | None = None,
        output_dir: str = "./output",
    ) -> None:
        """Run scraper in Docker container."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        env = []
        if config:
            env = ["-e", f"KNOWSCRAPER_INPUT={json.dumps(config.to_dict())}"]

        subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{Path(output_dir).absolute()}:/app/.knowscraper",
                *env,
                tag,
            ],
            check=True,
        )

    @staticmethod
    def get_input() -> RunConfig:
        """
        Get run configuration from the environment.
        Use this in your scraper to support both local and cloud runs.

        Example:
            config = KnowPlatform.get_input()
            await crawler.run(config.start_urls)
        """
        return RunConfig.from_env()
