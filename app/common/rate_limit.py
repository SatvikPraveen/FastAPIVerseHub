# File: app/common/rate_limit.py
"""Sliding-window rate limiting on Redis sorted sets.

Each client/window pair is a ZSET whose members are request timestamps.  A
hit is one MULTI/EXEC transaction:

    ZREMRANGEBYSCORE key 0 (now - window)   -- drop expired entries
    ZADD key now member                      -- record this request
    ZCARD key                                -- count inside the window
    ZRANGE key 0 0 WITHSCORES                -- oldest entry -> reset time
    EXPIRE key window                        -- self-clean idle keys

so concurrent requests cannot race the way a GET/INCR pair does, and the
window slides continuously instead of resetting on a fixed boundary.
Rejected requests are removed again so they do not extend the penalty.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

import redis.asyncio as redis

from app.core.time import from_timestamp


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    retry_after: int  # seconds; 0 when allowed
    key: str
    member: str

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": self.reset_at.isoformat(),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class SlidingWindowRateLimiter:
    def __init__(self, client: redis.Redis, prefix: str = "ratelimit") -> None:
        self.client = client
        self.prefix = prefix

    def _key(self, key: str, window_seconds: int) -> str:
        return f"{self.prefix}:{window_seconds}s:{key}"

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        """Record one request against ``key`` and decide whether it is allowed."""
        now = time.time()
        redis_key = self._key(key, window_seconds)
        member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"

        pipe = self.client.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.zrange(redis_key, 0, 0, withscores=True)
        pipe.expire(redis_key, window_seconds + 1)
        _, _, count, oldest, _ = await pipe.execute()

        oldest_ts = float(oldest[0][1]) if oldest else now
        reset_at = from_timestamp(oldest_ts + window_seconds)

        if int(count) > limit:
            await self.client.zrem(redis_key, member)
            retry_after = max(1, math.ceil(oldest_ts + window_seconds - now))
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
                key=redis_key,
                member=member,
            )

        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=max(0, limit - int(count)),
            reset_at=reset_at,
            retry_after=0,
            key=redis_key,
            member=member,
        )

    async def release(self, decision: RateLimitDecision) -> None:
        """Undo a recorded hit (used when a later, stricter window rejects)."""
        await self.client.zrem(decision.key, decision.member)
