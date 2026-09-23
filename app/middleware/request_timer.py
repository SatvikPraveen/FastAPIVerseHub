# File: app/middleware/request_timer.py
"""Request context middleware (pure ASGI).

Responsibilities:

* assign or propagate a correlation id (``X-Request-ID``);
* expose it to handlers via ``request.state.request_id`` and to every log
  line via a contextvar;
* time the request and emit one structured access-log line;
* flag slow requests.

It is written as a raw ASGI callable rather than ``BaseHTTPMiddleware``
because the latter buffers streaming responses (SSE), breaks
``BackgroundTasks`` ordering and adds a task-switch per request.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette.datastructures import Headers, MutableHeaders

from app.core.config import settings
from app.core.logging import bind_request_context, clear_request_context, get_logger, request_id_var

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

logger = get_logger(__name__)

SLOW_REQUEST_THRESHOLD_SECONDS = settings.SLOW_REQUEST_THRESHOLD_SECONDS
REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def client_ip_from_scope(scope: Scope) -> str:
    """Best-effort client address honouring reverse-proxy headers."""
    headers = Headers(scope=scope)
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip
    client = scope.get("client")
    return client[0] if client else "unknown"


class RequestContextMiddleware:
    """Correlation id + timing + access log for HTTP and WebSocket scopes."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex

        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["correlation_id"] = request_id  # backwards-compatible alias

        token = request_id_var.set(request_id)
        bind_request_context(request_id=request_id)

        method = scope.get("method", scope["type"].upper())
        path = scope.get("path", "")
        started = time.perf_counter()
        status_code: int | None = None

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers.append(REQUEST_ID_HEADER, request_id)
                headers.append("X-Process-Time", f"{time.perf_counter() - started:.4f}")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration = time.perf_counter() - started
            logger.exception(
                "request failed",
                method=method,
                path=path,
                duration_ms=round(duration * 1000, 2),
                client_ip=client_ip_from_scope(scope),
            )
            raise
        else:
            duration = time.perf_counter() - started
            if scope["type"] == "http":
                log = logger.warning if (status_code or 0) >= 500 else logger.info
                log(
                    "request completed",
                    method=method,
                    path=path,
                    status=status_code,
                    duration_ms=round(duration * 1000, 2),
                    client_ip=client_ip_from_scope(scope),
                )
            if duration > SLOW_REQUEST_THRESHOLD_SECONDS:
                logger.warning(
                    "Slow request detected",
                    method=method,
                    path=path,
                    duration_ms=round(duration * 1000, 2),
                    threshold_s=SLOW_REQUEST_THRESHOLD_SECONDS,
                )
        finally:
            clear_request_context()
            request_id_var.reset(token)


# Backwards-compatible name used by earlier revisions and docs.
RequestTimingMiddleware = RequestContextMiddleware
