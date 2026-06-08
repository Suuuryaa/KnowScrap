"""Tests for Router — label dispatch, default handler, missing handler."""

import pytest
from knowscraper.core.request import Request
from knowscraper.core.router import Router, CrawlingContext


def make_context(label=None):
    return CrawlingContext(request=Request(url="https://example.com", label=label))


@pytest.mark.asyncio
async def test_default_handler_called():
    router = Router()
    called = []

    @router.default_handler
    async def default(ctx):
        called.append("default")

    await router.dispatch(make_context(label=None))
    assert called == ["default"]


@pytest.mark.asyncio
async def test_label_handler_called():
    router = Router()
    called = []

    @router.handler("product")
    async def product(ctx):
        called.append("product")

    @router.default_handler
    async def default(ctx):
        called.append("default")

    await router.dispatch(make_context(label="product"))
    assert called == ["product"]


@pytest.mark.asyncio
async def test_unmatched_label_falls_back_to_default():
    router = Router()
    called = []

    @router.default_handler
    async def default(ctx):
        called.append("default")

    await router.dispatch(make_context(label="unknown_label"))
    assert called == ["default"]


@pytest.mark.asyncio
async def test_no_handler_raises():
    router = Router()
    with pytest.raises(ValueError, match="No handler"):
        await router.dispatch(make_context())


@pytest.mark.asyncio
async def test_multiple_labels():
    router = Router()
    results = []

    @router.handler("a")
    async def handle_a(ctx):
        results.append("a")

    @router.handler("b")
    async def handle_b(ctx):
        results.append("b")

    await router.dispatch(make_context("a"))
    await router.dispatch(make_context("b"))
    assert results == ["a", "b"]


@pytest.mark.asyncio
async def test_context_has_request():
    router = Router()

    @router.default_handler
    async def handler(ctx):
        assert ctx.request.url == "https://example.com"

    await router.dispatch(make_context())


@pytest.mark.asyncio
async def test_handler_can_access_user_data():
    router = Router()
    captured = []

    @router.default_handler
    async def handler(ctx):
        captured.append(ctx.request.user_data.get("key"))

    ctx = CrawlingContext(
        request=Request(url="https://x.com", user_data={"key": "found"})
    )
    await router.dispatch(ctx)
    assert captured == ["found"]
