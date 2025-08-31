# Async/Await Best Practices

**File Location: `docs/async_best_practices.md`**

## Understanding Async in FastAPI

FastAPI is built on top of Starlette and is fully async-compatible. This guide covers best practices for writing efficient async code in your FastAPI applications.

## When to Use Async

### ✅ Use async for:

- **I/O operations**: Database queries, HTTP requests, file operations
- **Network calls**: External API calls, microservice communication
- **Waiting operations**: Rate limiting, delays, timeouts
- **Concurrent processing**: Multiple independent operations

### ❌ Don't use async for:

- **CPU-intensive tasks**: Complex calculations, data processing
- **Synchronous libraries**: Libraries without async support
- **Simple operations**: Basic string manipulation, basic math

## Basic Async Patterns

### 1. Basic Async Function

```python
from fastapi import FastAPI

app = FastAPI()

# Async endpoint
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # Database query (async)
    user = await db.get_user(user_id)
    return user

# Sync endpoint (still works)
@app.get("/health")
def health_check():
    return {"status": "ok"}
```

### 2. Database Operations

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    """Async database query"""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_user(db: AsyncSession, user_data: UserCreate):
    """Async database creation"""
    db_user = User(**user_data.dict())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
```

### 3. External API Calls

```python
import httpx
from fastapi import HTTPException

async def fetch_external_data(url: str) -> dict:
    """Async HTTP request"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="External API error")
```

## Advanced Async Patterns

### 1. Concurrent Operations with asyncio.gather

```python
import asyncio
from typing import List

async def get_user_with_courses_and_stats(user_id: int):
    """Execute multiple async operations concurrently"""
    user_task = get_user(user_id)
    courses_task = get_user_courses(user_id)
    stats_task = get_user_stats(user_id)

    # Run all operations concurrently
    user, courses, stats = await asyncio.gather(
        user_task,
        courses_task,
        stats_task,
        return_exceptions=True
    )

    # Handle potential exceptions
    if isinstance(user, Exception):
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": user,
        "courses": courses if not isinstance(courses, Exception) else [],
        "stats": stats if not isinstance(stats, Exception) else {}
    }
```

### 2. Rate Limiting with Semaphores

```python
import asyncio
from typing import List

# Global semaphore to limit concurrent operations
API_SEMAPHORE = asyncio.Semaphore(5)  # Max 5 concurrent requests

async def rate_limited_api_call(url: str) -> dict:
    """API call with rate limiting"""
    async with API_SEMAPHORE:
        return await fetch_external_data(url)

async def fetch_multiple_resources(urls: List[str]) -> List[dict]:
    """Fetch multiple URLs with rate limiting"""
    tasks = [rate_limited_api_call(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions and return valid results
    return [result for result in results if not isinstance(result, Exception)]
```

### 3. Background Tasks with Async

```python
from fastapi import BackgroundTasks
import asyncio

async def send_email_async(email: str, subject: str, body: str):
    """Async email sending"""
    # Simulate email sending delay
    await asyncio.sleep(2)
    print(f"Email sent to {email}: {subject}")

async def process_user_registration(user_data: UserCreate):
    """Process registration with background tasks"""
    # Create user (immediate)
    user = await create_user(user_data)

    # Send welcome email (background)
    asyncio.create_task(send_email_async(
        user.email,
        "Welcome!",
        f"Welcome {user.full_name}!"
    ))

    return user
```

### 4. WebSocket with Async

```python
from fastapi import WebSocket
import asyncio
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Async broadcast to all connections"""
        if not self.active_connections:
            return

        # Send to all connections concurrently
        tasks = [
            self.send_safe(connection, message)
            for connection in self.active_connections
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_safe(self, websocket: WebSocket, message: dict):
        """Send message with error handling"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            # Remove disconnected client
            self.disconnect(websocket)
```

### 5. Server-Sent Events with Async

```python
from fastapi.responses import StreamingResponse
import asyncio
import json

async def event_stream():
    """Async event generator"""
    while True:
        # Simulate getting new data
        data = await get_latest_notifications()

        if data:
            yield f"data: {json.dumps(data)}\n\n"

        # Wait before next check
        await asyncio.sleep(5)

@app.get("/sse/notifications")
async def stream_notifications():
    """Server-Sent Events endpoint"""
    return StreamingResponse(
        event_stream(),
        media_type="text/plain"
    )
```

## Database Best Practices

### 1. Async Database Sessions

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """Async database dependency"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### 2. Bulk Operations

```python
async def create_users_bulk(db: AsyncSession, users_data: List[UserCreate]):
    """Efficient bulk user creation"""
    users = [User(**user_data.dict()) for user_data in users_data]
    db.add_all(users)
    await db.commit()

    # Refresh all objects to get IDs
    for user in users:
        await db.refresh(user)

    return users

async def update_users_bulk(db: AsyncSession, updates: List[dict]):
    """Bulk update operations"""
    for update in updates:
        await db.execute(
            update(User).where(User.id == update["id"]).values(**update["data"])
        )
    await db.commit()
```

### 3. Connection Pooling

```python
from sqlalchemy.pool import QueuePool

# Configure connection pool
engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,          # Number of connections to maintain
    max_overflow=10,       # Additional connections when pool is full
    pool_pre_ping=True,    # Validate connections before use
    pool_recycle=3600,     # Recycle connections every hour
)
```

## Error Handling in Async Code

### 1. Exception Handling

```python
async def safe_async_operation(operation_func, *args, **kwargs):
    """Wrapper for safe async operations"""
    try:
        return await operation_func(*args, **kwargs)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Operation timed out")
    except Exception as e:
        logger.error(f"Async operation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Usage
@app.get("/users/{user_id}")
async def get_user_endpoint(user_id: int):
    return await safe_async_operation(get_user, user_id)
```

### 2. Timeout Handling

```python
import asyncio

async def get_user_with_timeout(user_id: int, timeout: float = 30.0):
    """Get user with timeout"""
    try:
        return await asyncio.wait_for(
            get_user(user_id),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
```

### 3. Circuit Breaker Pattern

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class AsyncCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise HTTPException(status_code=503, detail="Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise e

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def reset(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
```

## Performance Optimization

### 1. Connection Reuse

```python
# Bad: Creating new client for each request
async def bad_api_call():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com/data")

# Good: Reuse client across requests
class APIClient:
    def __init__(self):
        self.client = httpx.AsyncClient()

    async def get_data(self):
        return await self.client.get("https://api.example.com/data")

    async def close(self):
        await self.client.aclose()

# Use as dependency
api_client = APIClient()

@app.on_event("shutdown")
async def shutdown():
    await api_client.close()
```

### 2. Caching Async Results

```python
import asyncio
from functools import wraps
from typing import Dict, Any

# Simple async cache
async_cache: Dict[str, Any] = {}

def async_cache_decorator(expiry_seconds: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Check cache
            if cache_key in async_cache:
                cached_result, timestamp = async_cache[cache_key]
                if time.time() - timestamp < expiry_seconds:
                    return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            async_cache[cache_key] = (result, time.time())
            return result

        return wrapper
    return decorator

# Usage
@async_cache_decorator(expiry_seconds=600)
async def get_expensive_data(param: str):
    # Simulate expensive operation
    await asyncio.sleep(2)
    return {"data": f"result for {param}"}
```

## Testing Async Code

### 1. Async Test Setup

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_async_endpoint(async_client):
    response = await async_client.get("/users/1")
    assert response.status_code == 200
```

### 2. Mocking Async Functions

```python
from unittest.mock import AsyncMock
import pytest

@pytest.mark.asyncio
async def test_user_service():
    # Mock async database call
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.first.return_value = User(id=1, email="test@example.com")

    service = UserService(mock_db)
    user = await service.get_user(1)

    assert user.id == 1
    assert user.email == "test@example.com"
```

## Common Pitfalls and Solutions

### 1. Blocking Operations in Async Context

```python
# Bad: Blocking operation in async function
async def bad_function():
    time.sleep(5)  # Blocks the event loop!
    return "done"

# Good: Use async alternatives
async def good_function():
    await asyncio.sleep(5)  # Non-blocking
    return "done"

# For CPU-intensive tasks, use executor
import concurrent.futures

async def cpu_intensive_task():
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor()

    result = await loop.run_in_executor(
        executor,
        some_cpu_intensive_function,
        arg1, arg2
    )
    return result
```

### 2. Forgetting to Await

```python
# Bad: Forgetting await
async def bad_endpoint():
    user = get_user(1)  # Returns coroutine, not User!
    return user

# Good: Always await async functions
async def good_endpoint():
    user = await get_user(1)  # Returns User object
    return user
```

### 3. Creating Too Many Concurrent Operations

```python
# Bad: Unlimited concurrency
async def process_all_users():
    users = await get_all_users()  # Could be thousands!
    tasks = [process_user(user) for user in users]
    await asyncio.gather(*tasks)  # May overwhelm system

# Good: Limited concurrency
async def process_all_users_limited():
    users = await get_all_users()
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent operations

    async def process_with_limit(user):
        async with semaphore:
            return await process_user(user)

    tasks = [process_with_limit(user) for user in users]
    await asyncio.gather(*tasks)
```

## Monitoring and Debugging

### 1. Async Performance Monitoring

```python
import time
import functools

def async_timer(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start
            logger.info(f"{func.__name__} took {duration:.2f}s")
    return wrapper

# Usage
@async_timer
async def slow_operation():
    await asyncio.sleep(2)
    return "done"
```

### 2. Debug Async Issues

```python
import asyncio
import logging

# Enable asyncio debug mode
logging.getLogger("asyncio").setLevel(logging.DEBUG)

# Check for running tasks
async def debug_tasks():
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    print(f"Running tasks: {len(tasks)}")
    for task in tasks:
        print(f"  - {task.get_name()}: {task}")
```

## Summary

1. **Use async for I/O operations**, not CPU-intensive tasks
2. **Always await async functions**
3. **Use asyncio.gather() for concurrent operations**
4. **Implement proper error handling and timeouts**
5. **Limit concurrency to avoid overwhelming systems**
6. **Reuse connections and clients**
7. **Test async code properly with pytest-asyncio**
8. **Monitor performance and debug issues**
9. **Follow the async-all-the-way principle**
10. **Use background tasks for fire-and-forget operations**
