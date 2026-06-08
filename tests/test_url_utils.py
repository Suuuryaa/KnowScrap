"""Tests for URL utilities — normalization, extraction, domain checks."""

import pytest
from bs4 import BeautifulSoup
from knowscraper.utils.url_utils import normalize_url, extract_links, same_domain, get_domain


# --- normalize_url ---

def test_absolute_url_unchanged():
    assert normalize_url("https://example.com/page") == "https://example.com/page"


def test_relative_url_resolved():
    result = normalize_url("/about", "https://example.com")
    assert result == "https://example.com/about"


def test_relative_url_with_base_path():
    result = normalize_url("../page", "https://example.com/blog/post")
    assert result == "https://example.com/page"


def test_fragment_stripped():
    result = normalize_url("https://example.com/page#section")
    assert result == "https://example.com/page"


def test_javascript_link_returns_none():
    assert normalize_url("javascript:void(0)") is None


def test_mailto_returns_none():
    assert normalize_url("mailto:test@example.com") is None


def test_empty_string_returns_none():
    assert normalize_url("") is None


def test_hash_only_returns_none():
    assert normalize_url("#top") is None


def test_http_scheme_allowed():
    assert normalize_url("http://example.com") == "http://example.com"


def test_non_http_scheme_returns_none():
    assert normalize_url("ftp://files.example.com") is None


# --- extract_links ---

def test_extract_links_from_html():
    html = '<a href="/page1">One</a><a href="https://other.com">Two</a>'
    soup = BeautifulSoup(html, "html.parser")
    links = extract_links(soup, base_url="https://example.com")
    assert "https://example.com/page1" in links
    assert "https://other.com" in links


def test_extract_links_skips_invalid():
    html = '<a href="javascript:void(0)">bad</a><a href="/good">good</a>'
    soup = BeautifulSoup(html, "html.parser")
    links = extract_links(soup, base_url="https://example.com")
    assert len(links) == 1
    assert "https://example.com/good" in links


def test_extract_links_custom_selector():
    html = '<a href="/a">link</a><button data-href="/b">btn</button>'
    soup = BeautifulSoup(html, "html.parser")
    links = extract_links(soup, selector="a[href]", base_url="https://example.com")
    assert len(links) == 1


# --- same_domain ---

def test_same_domain_true():
    assert same_domain("https://example.com/a", "https://example.com/b") is True


def test_same_domain_false():
    assert same_domain("https://example.com", "https://other.com") is False


def test_same_domain_subdomain_is_different():
    assert same_domain("https://example.com", "https://sub.example.com") is False


# --- get_domain ---

def test_get_domain():
    assert get_domain("https://example.com/path") == "example.com"


def test_get_domain_with_port():
    assert get_domain("https://example.com:8080/path") == "example.com:8080"
