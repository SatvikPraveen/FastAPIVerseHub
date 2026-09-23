# File: app/tests/test_rate_limit.py
"""Sliding-window rate limiter: unit level and through the middleware."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.common.rate_limit import SlidingWindowRateLimiter
from app.core.config import settings


class TestSlidingWindowRateLimiter:
    async def test_allows_up_to_limit_then_blocks(self, mock_redis):
        limiter = SlidingWindowRateLimiter(mock_redis)
        decisions = [await limiter.hit("client-a", limit=3, window_seconds=60) for _ in range(4)]

        assert [d.allowed for d in decisions] == [True, True, True, False]
        assert [d.remaining for d in decisions] == [2, 1, 0, 0]
        assert decisions[-1].retry_after >= 1
        assert decisions[-1].headers["Retry-After"] == str(decisions[-1].retry_after)

    async def test_rejected_requests_do_not_count(self, mock_redis):
        limiter = SlidingWindowRateLimiter(mock_redis)
        for _ in range(3):
            await limiter.hit("client-b", limit=3, window_seconds=60)
        for _ in range(5):
            await limiter.hit("client-b", limit=3, window_seconds=60)
        assert await mock_redis.zcard("ratelimit:60s:client-b") == 3

    async def test_window_slides(self, mock_redis):
        limiter = SlidingWindowRateLimiter(mock_redis)
        for _ in range(2):
            assert (await limiter.hit("client-c", limit=2, window_seconds=1)).allowed
        assert not (await limiter.hit("client-c", limit=2, window_seconds=1)).allowed
        await asyncio.sleep(1.05)
        assert (await limiter.hit("client-c", limit=2, window_seconds=1)).allowed

    async def test_release_undoes_a_hit(self, mock_redis):
        limiter = SlidingWindowRateLimiter(mock_redis)
        decision = await limiter.hit("client-d", limit=1, window_seconds=60)
        await limiter.release(decision)
        assert (await limiter.hit("client-d", limit=1, window_seconds=60)).allowed

    async def test_concurrent_hits_never_exceed_limit(self, mock_redis):
        limiter = SlidingWindowRateLimiter(mock_redis)
        results = await asyncio.gather(
            *(limiter.hit("client-e", limit=10, window_seconds=60) for _ in range(40))
        )
        assert sum(1 for r in results if r.allowed) == 10


@pytest.fixture
async def strict_app(mock_redis, db_session, monkeypatch):
    """A fresh application with a very low per-minute allowance."""
    from app.core.dependencies import get_db, get_redis
    from app.main import create_application

    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_BURST", 100)
    app = create_application()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis
    return app


class TestRateLimitMiddleware:
    async def test_returns_429_with_headers_when_exceeded(self, strict_app):
        async with AsyncClient(
            transport=ASGITransport(app=strict_app), base_url="http://test"
        ) as client:
            first = await client.get("/")
            second = await client.get("/")
            third = await client.get("/")

        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "2"
        assert first.headers["X-RateLimit-Remaining"] == "1"
        assert second.headers["X-RateLimit-Remaining"] == "0"

        assert third.status_code == 429
        assert third.json()["error"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in third.headers
        assert third.headers["X-RateLimit-Remaining"] == "0"
        # correlation id survives the short-circuit path
        assert "X-Request-ID" in third.headers

    async def test_clients_are_isolated(self, strict_app):
        async with AsyncClient(
            transport=ASGITransport(app=strict_app), base_url="http://test"
        ) as client:
            for _ in range(3):
                await client.get("/", headers={"X-Forwarded-For": "10.0.0.1"})
            other = await client.get("/", headers={"X-Forwarded-For": "10.0.0.2"})
        assert other.status_code == 200

    async def test_health_and_metrics_are_exempt(self, strict_app):
        async with AsyncClient(
            transport=ASGITransport(app=strict_app), base_url="http://test"
        ) as client:
            for _ in range(5):
                assert (await client.get("/health/live")).status_code == 200
            assert (await client.get("/metrics")).status_code == 200

    async def test_fails_open_when_redis_unavailable(self, strict_app, monkeypatch):
        from redis.exceptions import ConnectionError as RedisConnectionError

        from app.common.cache_utils import cache_manager

        async def broken():
            raise RedisConnectionError("redis down")

        monkeypatch.setattr(cache_manager, "get_redis", broken)
        async with AsyncClient(
            transport=ASGITransport(app=strict_app), base_url="http://test"
        ) as client:
            responses = [await client.get("/") for _ in range(5)]
        assert all(r.status_code == 200 for r in responses)
        assert "X-RateLimit-Limit" not in responses[0].headers
