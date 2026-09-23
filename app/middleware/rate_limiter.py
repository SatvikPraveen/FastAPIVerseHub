# File: app/middleware/rate_limiter.py
"""Rate limiting middleware (pure ASGI) over :mod:`app.common.rate_limit`.

Three sliding windows are evaluated per client, strictest first:

* burst  - ``RATE_LIMIT_BURST`` requests per 10 seconds
* minute - ``RATE_LIMIT_PER_MINUTE`` requests per 60 seconds
* hour   - 60x the per-minute allowance

Clients are identified by API key, then authenticated user, then IP.  If
Redis is unreachable the middleware fails *open* and logs a warning: an
outage in the cache tier must degrade throttling, not availability.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

from redis.exceptions import RedisError
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from app.common.cache_utils import cache_manager
from app.common.rate_limit import RateLimitDecision, SlidingWindowRateLimiter
from app.core.config import settings
from app.core.logging import get_logger
from app.middleware.request_timer import client_ip_from_scope

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

logger = get_logger(__name__)

DEFAULT_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {"/health", "/health/live", "/health/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
)


@dataclass(frozen=True, slots=True)
class Window:
    name: str
    seconds: int
    limit: int


class RateLimitMiddleware:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        calls_per_minute: int | None = None,
        calls_per_hour: int | None = None,
        burst_limit: int | None = None,
        exclude_paths: frozenset[str] | set[str] | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.app = app
        per_minute = calls_per_minute or settings.RATE_LIMIT_PER_MINUTE
        per_hour = calls_per_hour or per_minute * 60
        burst = settings.RATE_LIMIT_BURST if burst_limit is None else burst_limit
        self.windows: list[Window] = []
        if burst:
            self.windows.append(Window("burst", 10, burst))
        self.windows.append(Window("minute", 60, per_minute))
        self.windows.append(Window("hour", 3600, per_hour))
        self.exclude_paths = frozenset(exclude_paths or DEFAULT_EXCLUDED_PATHS)
        self.enabled = settings.RATE_LIMIT_ENABLED if enabled is None else enabled

    # ------------------------------------------------------------------

    @staticmethod
    def client_identifier(scope: Scope) -> str:
        headers = Headers(scope=scope)
        api_key = headers.get("x-api-key")
        if api_key:
            return f"api:{api_key[:16]}"
        user_id = scope.get("state", {}).get("user_id")
        if user_id:
            return f"user:{user_id}"
        return f"ip:{client_ip_from_scope(scope)}"

    async def evaluate(self, client_id: str) -> RateLimitDecision:
        """Hit every window; on rejection, roll back the earlier windows' hits.

        The decision returned for an allowed request is the *minute* window's,
        which is what clients care about for pacing.
        """
        limiter = SlidingWindowRateLimiter(await cache_manager.get_redis())
        accepted: list[RateLimitDecision] = []
        reported: RateLimitDecision | None = None
        for window in self.windows:
            decision = await limiter.hit(client_id, window.limit, window.seconds)
            if not decision.allowed:
                for earlier in accepted:
                    await limiter.release(earlier)
                return decision
            accepted.append(decision)
            if window.name == "minute":
                reported = decision
        return reported or accepted[-1]

    # ------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled or scope.get("path") in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        client_id = self.client_identifier(scope)
        try:
            decision = await self.evaluate(client_id)
        except (RedisError, OSError) as exc:
            logger.warning("rate limiter unavailable, failing open", error=str(exc))
            await self.app(scope, receive, send)
            return

        if not decision.allowed:
            logger.info(
                "rate limit exceeded",
                client=client_id,
                path=scope.get("path"),
                retry_after=decision.retry_after,
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests",
                    "details": {"retry_after": decision.retry_after},
                    "request_id": scope.get("state", {}).get("request_id"),
                },
                headers=decision.headers,
            )
            await response(scope, receive, send)
            return

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in decision.headers.items():
                    headers.append(name, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
