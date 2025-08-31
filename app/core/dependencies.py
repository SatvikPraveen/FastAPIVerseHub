# File: app/core/dependencies.py

from typing import AsyncGenerator, Optional

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import security_manager
from app.models.user import User

# Database setup
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Redis setup
redis_client: Optional[redis.Redis] = None

# Security
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    """Dependency for Redis client."""
    global redis_client
    
    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    return redis_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user."""
    try:
        # Verify access token
        payload = security_manager.verify_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        from app.services.user_service import UserService
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency to get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
):
    """Optional dependency to get current user if authenticated."""
    async def _get_user():
        if not credentials:
            return None
        
        try:
            payload = security_manager.verify_access_token(credentials.credentials)
            user_id = int(payload.get("sub"))
            
            if user_id is None:
                return None
            
            from app.services.user_service import UserService
            user_service = UserService(db)
            user = await user_service.get_user_by_id(user_id)
            
            return user if user and user.is_active else None
            
        except Exception:
            return None
    
    return _get_user


def get_request_id(request: Request) -> str:
    """Get or generate request ID."""
    return getattr(request.state, "request_id", "unknown")


def get_user_agent(request: Request) -> str:
    """Get user agent from request."""
    return request.headers.get("user-agent", "unknown")


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    # Check for forwarded IP first (from reverse proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fall back to client host
    if request.client:
        return request.client.host
    
    return "unknown"


class PaginationParams:
    """Pagination parameters for API endpoints."""
    
    def __init__(self, skip: int = 0, limit: int = 100):
        self.skip = max(0, skip)
        self.limit = min(100, max(1, limit))
    
    @property
    def offset(self) -> int:
        return self.skip
    
    @property
    def page_size(self) -> int:
        return self.limit


def get_pagination_params(skip: int = 0, limit: int = 100) -> PaginationParams:
    """Dependency for pagination parameters."""
    return PaginationParams(skip, limit)


class SearchParams:
    """Search parameters for API endpoints."""
    
    def __init__(self, q: Optional[str] = None, sort_by: Optional[str] = None, order: str = "asc"):
        self.query = q.strip() if q else None
        self.sort_by = sort_by
        self.order = order.lower() if order.lower() in ["asc", "desc"] else "asc"


def get_search_params(
    q: Optional[str] = None, 
    sort_by: Optional[str] = None, 
    order: str = "asc"
) -> SearchParams:
    """Dependency for search parameters."""
    return SearchParams(q, sort_by, order)


async def close_db_connection():
    """Close database connections on shutdown."""
    if engine:
        await engine.dispose()


async def close_redis_connection():
    """Close Redis connection on shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()