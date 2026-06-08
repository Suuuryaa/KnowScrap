"""Tests for KnowPlatform and RunConfig."""

import json
import os
import pytest
from pathlib import Path
from knowscraper.platform import KnowPlatform, RunConfig


# ── RunConfig ─────────────────────────────────────────────────────────────────

class TestRunConfig:
    def test_defaults(self):
        cfg = RunConfig()
        assert cfg.start_urls == []
        assert cfg.max_pages is None
        assert cfg.max_concurrency == 10
        assert cfg.use_anti_detection is True
        assert cfg.headless is True

    def test_from_dict(self):
        cfg = RunConfig.from_dict({
            "startUrls": ["https://a.com"],
            "maxPages": 50,
            "maxConcurrency": 5,
            "headless": False,
        })
        assert cfg.start_urls == ["https://a.com"]
        assert cfg.max_pages == 50
        assert cfg.max_concurrency == 5
        assert cfg.headless is False

    def test_from_dict_snake_case(self):
        cfg = RunConfig.from_dict({
            "start_urls": ["https://b.com"],
            "max_concurrency": 3,
        })
        assert cfg.start_urls == ["https://b.com"]
        assert cfg.max_concurrency == 3

    def test_from_env(self, monkeypatch):
        payload = json.dumps({
            "startUrls": ["https://env.com"],
            "maxPages": 10,
        })
        monkeypatch.setenv("KNOWSCRAPER_INPUT", payload)
        cfg = RunConfig.from_env()
        assert cfg.start_urls == ["https://env.com"]
        assert cfg.max_pages == 10

    def test_from_env_empty(self, monkeypatch):
        monkeypatch.delenv("KNOWSCRAPER_INPUT", raising=False)
        cfg = RunConfig.from_env()
        assert cfg.start_urls == []

    def test_from_env_invalid_json(self, monkeypatch):
        monkeypatch.setenv("KNOWSCRAPER_INPUT", "not-json")
        cfg = RunConfig.from_env()
        assert cfg.start_urls == []

    def test_from_file(self, tmp_path):
        data = {"startUrls": ["https://file.com"], "maxPages": 5}
        f = tmp_path / "input.json"
        f.write_text(json.dumps(data))
        cfg = RunConfig.from_file(str(f))
        assert cfg.start_urls == ["https://file.com"]
        assert cfg.max_pages == 5

    def test_to_dict_round_trip(self):
        cfg = RunConfig(
            start_urls=["https://x.com"],
            max_pages=100,
            max_concurrency=8,
        )
        restored = RunConfig.from_dict(cfg.to_dict())
        assert restored.start_urls == cfg.start_urls
        assert restored.max_pages == cfg.max_pages
        assert restored.max_concurrency == cfg.max_concurrency

    def test_custom_fields(self):
        cfg = RunConfig.from_dict({
            "startUrls": ["https://x.com"],
            "myCustomField": "hello",
        })
        assert cfg.custom.get("myCustomField") == "hello"


# ── KnowPlatform ──────────────────────────────────────────────────────────────

class TestKnowPlatform:
    @pytest.fixture
    def platform(self, tmp_path):
        return KnowPlatform(project_dir=str(tmp_path))

    def test_generate_dockerfile(self, platform, tmp_path):
        path = platform.generate_dockerfile()
        assert path.exists()
        content = path.read_text()
        assert "FROM python:3.12-slim" in content
        assert "playwright install" in content
        assert "npm install" in content

    def test_generate_docker_compose(self, platform, tmp_path):
        path = platform.generate_docker_compose()
        assert path.exists()
        content = path.read_text()
        assert "scraper:" in content
        assert "KNOWSCRAPER_INPUT" in content

    def test_generate_github_action(self, platform, tmp_path):
        path = platform.generate_github_action()
        assert path.exists()
        content = path.read_text()
        assert "actions/checkout" in content
        assert "playwright install" in content
        assert "cron:" in content

    def test_generate_input_schema(self, platform, tmp_path):
        path = platform.generate_input_schema()
        assert path.exists()
        schema = json.loads(path.read_text())
        assert schema["type"] == "object"
        assert "startUrls" in schema["properties"]
        assert "startUrls" in schema["required"]

    def test_generate_to_custom_path(self, platform, tmp_path):
        out = tmp_path / "custom" / "Dockerfile"
        out.parent.mkdir()
        path = platform.generate_dockerfile(output=str(out))
        assert path == out
        assert out.exists()
