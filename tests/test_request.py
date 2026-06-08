"""Tests for Request and RequestState."""

import pytest
from knowscraper.core.request import Request, RequestState


def test_request_default_state():
    r = Request(url="https://example.com")
    assert r.state == RequestState.PENDING
    assert r.retry_count == 0
    assert r.method == "GET"


def test_request_unique_key_generated():
    r = Request(url="https://example.com")
    assert len(r.unique_key) == 64  # sha256 hex


def test_same_url_same_key():
    r1 = Request(url="https://example.com")
    r2 = Request(url="https://example.com")
    assert r1.unique_key == r2.unique_key


def test_different_url_different_key():
    r1 = Request(url="https://example.com/a")
    r2 = Request(url="https://example.com/b")
    assert r1.unique_key != r2.unique_key


def test_mark_failed_increments_retry():
    r = Request(url="https://example.com", max_retries=3)
    r.mark_failed()
    assert r.retry_count == 1
    assert r.state == RequestState.PENDING  # still retryable


def test_mark_failed_exhausts_retries():
    r = Request(url="https://example.com", max_retries=2)
    r.mark_failed()
    r.mark_failed()
    assert r.retry_count == 2
    assert r.state == RequestState.FAILED
    assert not r.can_retry


def test_mark_done():
    r = Request(url="https://example.com")
    r.mark_done()
    assert r.state == RequestState.DONE


def test_to_dict_roundtrip():
    r = Request(url="https://example.com", label="test", user_data={"key": "val"})
    d = r.to_dict()
    r2 = Request.from_dict(d)
    assert r2.url == r.url
    assert r2.label == r.label
    assert r2.user_data == r.user_data
    assert r2.unique_key == r.unique_key


def test_custom_unique_key():
    r = Request(url="https://example.com", unique_key="custom-key")
    assert r.unique_key == "custom-key"


def test_label_default_none():
    r = Request(url="https://example.com")
    assert r.label is None
