# File: app/api/health.py
"""Liveness and readiness probes.

* ``/health/live``  - the process is up (never touches dependencies), for
  container restart policies.
* ``/health/ready`` - the database and Redis answer within
  ``HEALTH_CHECK_TIMEOUT``; returns 503 otherwise so load balancers stop
  routing traffic here without killing the pod.
* ``/health``       - legacy summary, kept for existing dashboards.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.cache_utils import cache_manager
from app.core.config import settings
from app.core.dependencies import get_db
from app.core.time import utcnow

router = APIRouter(tags=["Health"])


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    started = time.perf_counter()
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


async def _check_redis() -> dict[str, Any]:
    started = time.perf_counter()
    client = await cache_manager.get_redis()
    await client.ping()
    return {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


async def _guarded(name: str, coro: Any) -> tuple[str, dict[str, Any]]:
    try:
        result = await asyncio.wait_for(coro, timeout=settings.HEALTH_CHECK_TIMEOUT)
    except TimeoutError:
        return name, {"status": "timeout", "timeout_s": settings.HEALTH_CHECK_TIMEOUT}
    except Exception as exc:
        return name, {"status": "error", "error": type(exc).__name__}
    return name, result


def _uptime_seconds(request: Request) -> float | None:
    started_at = getattr(request.app.state, "started_at", None)
    return round(time.time() - started_at, 1) if started_at else None


@router.get("/health/live", summary="Liveness probe")
async def liveness(request: Request) -> dict[str, Any]:
    return {
        "status": "alive",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": _uptime_seconds(request),
        "timestamp": utcnow(),
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    responses={503: {"description": "One or more dependencies are unavailable"}},
)
async def readiness(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    checks = dict(
        await asyncio.gather(
            _guarded("database", _check_database(db)),
            _guarded("redis", _check_redis()),
        )
    )
    ready = all(component["status"] == "ok" for component in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "degraded",
        "checks": checks,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": _uptime_seconds(request),
        "timestamp": utcnow(),
    }


@router.get("/health", summary="Health summary")
async def health(request: Request) -> dict[str, Any]:
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": _uptime_seconds(request),
        "probes": {"live": "/health/live", "ready": "/health/ready"},
    }
