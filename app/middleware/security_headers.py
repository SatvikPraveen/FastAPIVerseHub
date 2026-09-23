# File: app/middleware/security_headers.py
"""Baseline HTTP security headers (pure ASGI).

The reverse proxy normally adds these too, but the API should be safe on
its own when exposed directly (local docker-compose, preview environments).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette.datastructures import MutableHeaders

from app.core.config import settings

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

DEFAULT_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# Swagger / ReDoc load assets from a CDN; a strict CSP would blank the page.
_DOCS_PATHS = ("/docs", "/redoc", "/docs/oauth2-redirect")


class SecurityHeadersMiddleware:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        headers: dict[str, str] | None = None,
        hsts: bool | None = None,
        hsts_max_age: int = 31536000,
    ) -> None:
        self.app = app
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.hsts = settings.is_production if hsts is None else hsts
        self.hsts_max_age = hsts_max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_docs = scope.get("path", "") in _DOCS_PATHS

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    if name not in headers:
                        headers.append(name, value)
                if not is_docs and "Content-Security-Policy" not in headers:
                    headers.append(
                        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                    )
                if self.hsts:
                    headers.append(
                        "Strict-Transport-Security",
                        f"max-age={self.hsts_max_age}; includeSubDomains",
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)
