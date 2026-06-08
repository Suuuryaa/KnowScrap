"""Tests for SessionPool — session lifecycle, retirement, blocking."""

import pytest
from knowscraper.core.session_pool import Session, SessionPool, BLOCKED_STATUS_CODES


@pytest.mark.asyncio
async def test_get_session_creates_new():
    pool = SessionPool(max_pool_size=5)
    session = await pool.get_session()
    assert session is not None
    assert session.use_count == 1


@pytest.mark.asyncio
async def test_session_reused_from_pool():
    pool = SessionPool(max_pool_size=5)
    s1 = await pool.get_session()
    s2 = await pool.get_session()
    # With only 2 gets, should reuse the same session
    assert s1.id == s2.id
    assert s2.use_count == 2


@pytest.mark.asyncio
async def test_session_retired_after_max_uses():
    pool = SessionPool(max_pool_size=5, max_session_uses=2)
    s = await pool.get_session()
    await pool.get_session()  # use_count = 2 (max)

    # Now it's at max — next get should create new session
    s3 = await pool.get_session()
    assert s3.id != s.id


@pytest.mark.asyncio
async def test_retire_session():
    pool = SessionPool()
    session = await pool.get_session()
    await pool.retire_session(session)
    assert session.retired is True


@pytest.mark.asyncio
async def test_block_on_403():
    pool = SessionPool(max_session_errors=1)
    session = await pool.get_session()
    blocked = pool.mark_session_blocked(session, 403)
    assert blocked is True
    assert session.retired is True


@pytest.mark.asyncio
async def test_no_block_on_200():
    pool = SessionPool()
    session = await pool.get_session()
    blocked = pool.mark_session_blocked(session, 200)
    assert blocked is False
    assert not session.retired


@pytest.mark.asyncio
async def test_blocked_status_codes_covered():
    pool = SessionPool(max_session_errors=1)
    for code in BLOCKED_STATUS_CODES:
        session = Session(id=f"s_{code}", max_errors=1)
        pool.mark_session_blocked(session, code)
        assert session.retired, f"Expected session retired for status {code}"


@pytest.mark.asyncio
async def test_pool_stats():
    pool = SessionPool(max_pool_size=10)
    await pool.get_session()
    await pool.get_session()
    stats = pool.stats
    assert stats["total"] >= 1
    assert stats["usable"] >= 1


@pytest.mark.asyncio
async def test_session_is_usable():
    s = Session(id="test", max_uses=5, max_errors=3)
    assert s.is_usable is True
    s.use_count = 5
    assert s.is_usable is False


@pytest.mark.asyncio
async def test_session_error_retirement():
    s = Session(id="test", max_errors=2)
    s.record_error()
    assert s.is_usable is True
    s.record_error()
    assert s.retired is True
