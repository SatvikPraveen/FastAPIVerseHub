# File: app/tests/test_health.py
"""Liveness / readiness probes."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.common.cache_utils import cache_manager


async def test_liveness_never_touches_dependencies(async_client: AsyncClient):
    with patch.object(cache_manager, "get_redis", side_effect=AssertionError("must not be called")):
        response = await async_client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"
    assert "version" in body


async def test_readiness_ok_when_dependencies_answer(async_client: AsyncClient):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"
    assert body["checks"]["redis"]["latency_ms"] >= 0


async def test_readiness_503_when_redis_down(async_client: AsyncClient):
    broken = AsyncMock()
    broken.ping.side_effect = ConnectionError("redis down")
    with patch.object(cache_manager, "get_redis", AsyncMock(return_value=broken)):
        response = await async_client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"]["status"] == "error"
    assert body["checks"]["database"]["status"] == "ok"


async def test_readiness_reports_timeouts(async_client: AsyncClient, monkeypatch):
    import asyncio

    from app.core.config import settings

    async def slow_ping():
        await asyncio.sleep(1)

    slow = AsyncMock()
    slow.ping.side_effect = slow_ping
    monkeypatch.setattr(settings, "HEALTH_CHECK_TIMEOUT", 0.05)
    with patch.object(cache_manager, "get_redis", AsyncMock(return_value=slow)):
        response = await async_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"]["status"] == "timeout"


async def test_legacy_health_summary(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["probes"] == {"live": "/health/live", "ready": "/health/ready"}
