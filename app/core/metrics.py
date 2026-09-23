# File: app/core/metrics.py
"""Prometheus instrumentation.

A pure-ASGI middleware records request counts, latency histograms and
in-flight gauges keyed by the *route template* (``/api/v1/courses/{id}``),
never the raw path, so label cardinality stays bounded.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being handled",
    ["method"],
)
EXCEPTIONS_TOTAL = Counter(
    "http_exceptions_total",
    "Unhandled exceptions raised while handling requests",
    ["method", "path", "exception"],
)

UNMATCHED_ROUTE = "unmatched"


def route_template(scope: Scope, root_path_before: str = "") -> str:
    """Return the matched route's template, or a constant for 404s.

    FastAPI (>= 0.120) resolves included routers through an "effective route
    context" that carries the fully prefixed template
    (``/api/v1/courses/{course_id}``); ``scope["route"]`` holds the original,
    unprefixed route object.  Prefer the former, fall back to the latter, and
    re-attach any mount prefix pushed onto ``root_path`` during routing.
    """
    context = (scope.get("fastapi") or {}).get("effective_route_context")
    template = str(getattr(context, "path_format", "") or "")
    if not template:
        route = scope.get("route")
        if route is None:
            return UNMATCHED_ROUTE
        template = str(getattr(route, "path_format", None) or getattr(route, "path", ""))
    mounted_prefix = scope.get("root_path", "")[len(root_path_before) :]
    return (mounted_prefix + template) or UNMATCHED_ROUTE


class PrometheusMiddleware:
    def __init__(
        self, app: Callable[..., Awaitable[None]], exclude_paths: tuple[str, ...] = ("/metrics",)
    ) -> None:
        self.app = app
        self.exclude_paths = exclude_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        status_code = 500
        started = time.perf_counter()
        root_path_before = scope.get("root_path", "")
        REQUESTS_IN_PROGRESS.labels(method=method).inc()

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            EXCEPTIONS_TOTAL.labels(
                method=method,
                path=route_template(scope, root_path_before),
                exception=type(exc).__name__,
            ).inc()
            raise
        finally:
            path = route_template(scope, root_path_before)
            REQUESTS_IN_PROGRESS.labels(method=method).dec()
            REQUEST_DURATION.labels(method=method, path=path).observe(time.perf_counter() - started)
            REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()


router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
