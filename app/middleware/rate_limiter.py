# File: app/middleware/rate_limiter.py

import time
from typing import Callable, Dict, Optional
from datetime import datetime, timedelta

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.common.cache_utils import cache_manager, RateLimitCache
from app.core.config import settings
from app.exceptions.base_exceptions import RateLimitException


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with multiple strategies."""
    
    def __init__(
        self,
        app,
        calls_per_minute: int = None,
        calls_per_hour: int = None,
        burst_limit: int = None,
        exclude_paths: list = None
    ):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.calls_per_hour = calls_per_hour or (self.calls_per_minute * 60)
        self.burst_limit = burst_limit or settings.RATE_LIMIT_BURST
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]
        self.rate_limit_cache = RateLimitCache(cache_manager)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check rate limits
        rate_limit_info = await self._check_rate_limits(client_id, request)
        
        if rate_limit_info["blocked"]:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests",
                    "retry_after": rate_limit_info["retry_after"]
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
                    "X-RateLimit-Reset": rate_limit_info["reset_time"],
                    "Retry-After": str(rate_limit_info["retry_after"])
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = rate_limit_info["reset_time"]
        
        return response
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier for rate limiting."""
        # Priority order: API key, user ID, IP address
        
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key[:10]}"
        
        # Check for authenticated user
        if hasattr(request.state, "user_id") and request.state.user_id:
            return f"user:{request.state.user_id}"
        
        # Fall back to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        # Check forwarded headers first (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _check_rate_limits(self, client_id: str, request: Request) -> Dict:
        """Check multiple rate limit windows."""
        current_time = datetime.utcnow()
        
        # Define rate limit windows
        limits = [
            {
                "window": 60,  # 1 minute
                "limit": self.calls_per_minute,
                "key": f"rate_limit:1m:{client_id}"
            },
            {
                "window": 3600,  # 1 hour  
                "limit": self.calls_per_hour,
                "key": f"rate_limit:1h:{client_id}"
            }
        ]
        
        # Check burst limit (short window, high limit)
        if self.burst_limit:
            limits.insert(0, {
                "window": 10,  # 10 seconds
                "limit": self.burst_limit,
                "key": f"rate_limit:10s:{client_id}"
            })
        
        # Check each limit
        for limit_config in limits:
            is_limited, info = await self.rate_limit_cache.is_rate_limited(
                limit_config["key"],
                limit_config["limit"],
                limit_config["window"]
            )
            
            if is_limited:
                return {
                    "blocked": True,
                    "limit": limit_config["limit"],
                    "remaining": info["remaining"],
                    "reset_time": info["reset_at"].isoformat(),
                    "retry_after": info["retry_after"],
                    "window": limit_config["window"]
                }
        
        # If not limited, return info from the most restrictive limit (1 minute)
        minute_limit = limits[1] if self.burst_limit else limits[0]
        _, info = await self.rate_limit_cache.is_rate_limited(
            minute_limit["key"],
            minute_limit["limit"],
            minute_limit["window"]
        )
        
        return {
            "blocked": False,
            "limit": minute_limit["limit"],
            "remaining": info["remaining"],
            "reset_time": info["reset_at"].isoformat(),
            "retry_after": 0,
            "window": minute_limit["window"]
        }


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts limits based on system load."""
    
    def __init__(self):
        self.base_limit = settings.RATE_LIMIT_PER_MINUTE
        self.load_factor = 1.0
        self.last_adjustment = datetime.utcnow()
    
    async def get_current_limit(self, client_type: str = "default") -> int:
        """Get current rate limit based on system load."""
        await self._adjust_for_load()
        
        # Different limits for different client types
        multipliers = {
            "api_key": 2.0,      # API keys get higher limits
            "authenticated": 1.5,  # Authenticated users get moderate boost
            "default": 1.0       # Anonymous users get base limit
        }
        
        multiplier = multipliers.get(client_type, 1.0)
        return int(self.base_limit * self.load_factor * multiplier)
    
    async def _adjust_for_load(self):
        """Adjust rate limits based on system load."""
        now = datetime.utcnow()
        
        # Only adjust every minute
        if (now - self.last_adjustment).seconds < 60:
            return
        
        try:
            # Get system metrics (placeholder implementation)
            cpu_usage = await self._get_cpu_usage()
            memory_usage = await self._get_memory_usage()
            
            # Calculate load factor (0.5 to 2.0)
            if cpu_usage > 80 or memory_usage > 85:
                # High load - reduce limits
                self.load_factor = max(0.5, self.load_factor * 0.9)
            elif cpu_usage < 50 and memory_usage < 60:
                # Low load - increase limits
                self.load_factor = min(2.0, self.load_factor * 1.1)
            
            self.last_adjustment = now
            
        except Exception:
            # If we can't get metrics, use conservative approach
            self.load_factor = 1.0
    
    async def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        # Placeholder - would integrate with system monitoring
        return 50.0
    
    async def _get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        # Placeholder - would integrate with system monitoring  
        return 60.0


class EndpointRateLimiter:
    """Rate limiter with per-endpoint configuration."""
    
    def __init__(self):
        self.endpoint_limits = {
            # Authentication endpoints - stricter limits
            "/api/v1/auth/login": {"calls": 5, "window": 300},  # 5 calls per 5 minutes
            "/api/v1/auth/register": {"calls": 3, "window": 3600},  # 3 calls per hour
            "/api/v1/auth/reset-password": {"calls": 3, "window": 3600},
            
            # File upload endpoints - moderate limits
            "/api/v1/uploads/file": {"calls": 10, "window": 60},  # 10 uploads per minute
            "/api/v1/uploads/multiple": {"calls": 5, "window": 60},
            
            # Search endpoints - generous limits
            "/api/v1/courses": {"calls": 100, "window": 60},
            "/api/v1/users": {"calls": 50, "window": 60},
            
            # WebSocket connections - very strict
            "/api/v1/ws/connect": {"calls": 5, "window": 60},
        }
    
    async def check_endpoint_limit(
        self,
        endpoint: str,
        client_id: str
    ) -> tuple[bool, Dict]:
        """Check rate limit for specific endpoint."""
        
        # Get endpoint configuration
        config = self.endpoint_limits.get(endpoint)
        if not config:
            # No specific limit configured - use default
            return False, {"limit": float("inf"), "remaining": float("inf")}
        
        # Check limit
        key = f"endpoint:{endpoint}:{client_id}"
        is_limited, info = await cache_manager.get(f"rate_check:{key}", default=(False, {}))
        
        if not is_limited:
            # Simplified rate limiting logic
            current_count = await cache_manager.get(key, default=0)
            
            if current_count >= config["calls"]:
                return True, {
                    "limit": config["calls"],
                    "remaining": 0,
                    "window": config["window"]
                }
            
            # Increment counter
            await cache_manager.increment(key)
            await cache_manager.expire(key, config["window"])
            
            return False, {
                "limit": config["calls"],
                "remaining": config["calls"] - current_count - 1,
                "window": config["window"]
            }
        
        return is_limited, info


# Global instances
adaptive_limiter = AdaptiveRateLimiter()
endpoint_limiter = EndpointRateLimiter()