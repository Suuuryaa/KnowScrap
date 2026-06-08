"""Tests for ProxyConfiguration — rotation, parsing, httpx/playwright format."""

import pytest
from knowscraper.core.proxy_configuration import ProxyConfiguration, ProxyInfo


def test_no_proxies_returns_none():
    config = ProxyConfiguration()
    assert config.new_proxy_info() is None
    assert config.is_configured is False


def test_single_proxy_always_returned():
    config = ProxyConfiguration(proxy_urls=["http://proxy.example.com:8080"])
    for _ in range(5):
        info = config.new_proxy_info()
        assert info.hostname == "proxy.example.com"
        assert info.port == 8080


def test_round_robin_rotation():
    urls = [
        "http://proxy1.example.com:8080",
        "http://proxy2.example.com:8080",
        "http://proxy3.example.com:8080",
    ]
    config = ProxyConfiguration(proxy_urls=urls, rotate="round_robin")
    results = [config.new_proxy_info().hostname for _ in range(6)]
    assert results == [
        "proxy1.example.com",
        "proxy2.example.com",
        "proxy3.example.com",
        "proxy1.example.com",
        "proxy2.example.com",
        "proxy3.example.com",
    ]


def test_random_rotation_stays_in_set():
    urls = ["http://a.com:8080", "http://b.com:8080"]
    config = ProxyConfiguration(proxy_urls=urls, rotate="random")
    for _ in range(20):
        info = config.new_proxy_info()
        assert info.hostname in ("a.com", "b.com")


def test_proxy_with_auth_parsed():
    info = ProxyInfo.from_url("http://user:pass@proxy.com:3128")
    assert info.username == "user"
    assert info.password == "pass"
    assert info.hostname == "proxy.com"
    assert info.port == 3128


def test_to_httpx_format():
    info = ProxyInfo.from_url("http://proxy.example.com:8080")
    proxies = info.to_httpx()
    assert "http://" in proxies
    assert "https://" in proxies


def test_to_playwright_format():
    info = ProxyInfo.from_url("http://user:secret@proxy.com:9000")
    pw = info.to_playwright()
    assert pw["server"] == "http://proxy.com:9000"
    assert pw["username"] == "user"
    assert pw["password"] == "secret"


def test_to_playwright_no_auth():
    info = ProxyInfo.from_url("http://proxy.com:8080")
    pw = info.to_playwright()
    assert "username" not in pw
    assert "password" not in pw
