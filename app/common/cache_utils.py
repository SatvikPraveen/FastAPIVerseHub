# File: app/common/cache_utils.py

import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List
from functools import wraps

import redis.asyncio as redis
from app.core.config import settings


class CacheManager:
    """Redis cache manager with advanced features."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = 3600  # 1 hour
    
    async def get_redis(self) -> redis.Redis:
        """Get Redis client instance."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
        return self.redis_client
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        serialize: str = "json"
    ) -> bool:
        """Set cache value with optional TTL."""
        client = await self.get_redis()
        
        if serialize == "json":
            serialized_value = json.dumps(value, default=str)
        elif serialize == "pickle":
            serialized_value = pickle.dumps(value)
        else:
            serialized_value = str(value)
        
        ttl = ttl or self.default_ttl
        return await client.setex(key, ttl, serialized_value)
    
    async def get(
        self, 
        key: str, 
        default: Any = None,
        serialize: str = "json"
    ) -> Any:
        """Get cache value with deserialization."""
        client = await self.get_redis()
        value = await client.get(key)
        
        if value is None:
            return default
        
        try:
            if serialize == "json":
                return json.loads(value)
            elif serialize == "pickle":
                return pickle.loads(value)
            else:
                return value.decode() if isinstance(value, bytes) else value
        except Exception:
            return default
    
    async def delete(self, key: str) -> bool:
        """Delete cache key."""
        client = await self.get_redis()
        return await client.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        client = await self.get_redis()
        return await client.exists(key) > 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        client = await self.get_redis()
        return await client.expire(key, ttl)
    
    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        client = await self.get_redis()
        return await client.ttl(key)
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment numeric value."""
        client = await self.get_redis()
        return await client.incrby(key, amount)
    
    async def set_hash(self, key: str, mapping: Dict[str, Any], ttl: Optional[int] = None):
        """Set hash values."""
        client = await self.get_redis()
        
        # Serialize values in mapping
        serialized_mapping = {
            k: json.dumps(v, default=str) for k, v in mapping.items()
        }
        
        await client.hset(key, mapping=serialized_mapping)
        
        if ttl:
            await client.expire(key, ttl)
    
    async def get_hash(self, key: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get hash values."""
        client = await self.get_redis()
        
        if fields:
            values = await client.hmget(key, fields)
            result = {}
            for field, value in zip(fields, values):
                if value:
                    try:
                        result[field] = json.loads(value)
                    except:
                        result[field] = value
            return result
        else:
            hash_data = await client.hgetall(key)
            return {
                k.decode() if isinstance(k, bytes) else k: 
                json.loads(v) if v else None
                for k, v in hash_data.items()
            }
    
    async def add_to_set(self, key: str, *values: Any, ttl: Optional[int] = None):
        """Add values to set."""
        client = await self.get_redis()
        serialized_values = [json.dumps(v, default=str) for v in values]
        await client.sadd(key, *serialized_values)
        
        if ttl:
            await client.expire(key, ttl)
    
    async def get_set(self, key: str) -> List[Any]:
        """Get all values from set."""
        client = await self.get_redis()
        values = await client.smembers(key)
        return [json.loads(v) for v in values if v]
    
    async def remove_from_set(self, key: str, *values: Any) -> int:
        """Remove values from set."""
        client = await self.get_redis()
        serialized_values = [json.dumps(v, default=str) for v in values]
        return await client.srem(key, *serialized_values)
    
    async def push_to_list(self, key: str, *values: Any, ttl: Optional[int] = None):
        """Push values to list (left)."""
        client = await self.get_redis()
        serialized_values = [json.dumps(v, default=str) for v in values]
        await client.lpush(key, *serialized_values)
        
        if ttl:
            await client.expire(key, ttl)
    
    async def pop_from_list(self, key: str, count: int = 1) -> List[Any]:
        """Pop values from list (right)."""
        client = await self.get_redis()
        values = []
        for _ in range(count):
            value = await client.rpop(key)
            if value:
                values.append(json.loads(value))
        return values
    
    async def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get list range."""
        client = await self.get_redis()
        values = await client.lrange(key, start, end)
        return [json.loads(v) for v in values if v]
    
    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        client = await self.get_redis()
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        client = await self.get_redis()
        info = await client.info()
        
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory_human", "0B"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "total_commands_processed": info.get("total_commands_processed", 0)
        }


# Global cache manager instance
cache_manager = CacheManager()


def cached(
    ttl: int = 3600,
    key_prefix: str = "",
    serialize: str = "json"
):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, serialize=serialize)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl=ttl, serialize=serialize)
            
            return result
        return wrapper
    return decorator


class RateLimitCache:
    """Rate limiting using Redis."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    async def is_rate_limited(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, Dict[str, Any]]:
        """Check if key is rate limited."""
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=window_seconds)
        
        # Use sliding window counter
        pipe_key = f"rate_limit:{key}"
        
        # Get current count
        current_count = await self.cache.get(pipe_key, default=0)
        
        if current_count >= limit:
            ttl = await self.cache.ttl(pipe_key)
            return True, {
                "limit": limit,
                "remaining": 0,
                "reset_at": current_time + timedelta(seconds=ttl),
                "retry_after": ttl
            }
        
        # Increment counter
        new_count = await self.cache.increment(pipe_key)
        
        # Set expiration if this is the first increment
        if new_count == 1:
            await self.cache.expire(pipe_key, window_seconds)
        
        ttl = await self.cache.ttl(pipe_key)
        
        return False, {
            "limit": limit,
            "remaining": max(0, limit - new_count),
            "reset_at": current_time + timedelta(seconds=ttl),
            "retry_after": 0
        }


class SessionCache:
    """Session management using Redis."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.session_ttl = 86400  # 24 hours
    
    async def create_session(
        self,
        session_id: str,
        user_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """Create new session."""
        session_key = f"session:{session_id}"
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            **data
        }
        
        return await self.cache.set(session_key, session_data, ttl=self.session_ttl)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session_key = f"session:{session_id}"
        return await self.cache.get(session_key)
    
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Update session data."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False
        
        session_data.update(data)
        session_data["last_activity"] = datetime.utcnow().isoformat()
        
        session_key = f"session:{session_id}"
        return await self.cache.set(session_key, session_data, ttl=self.session_ttl)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        session_key = f"session:{session_id}"
        return await self.cache.delete(session_key)
    
    async def extend_session(self, session_id: str, extra_ttl: int = None) -> bool:
        """Extend session TTL."""
        session_key = f"session:{session_id}"
        ttl = extra_ttl or self.session_ttl
        return await self.cache.expire(session_key, ttl)