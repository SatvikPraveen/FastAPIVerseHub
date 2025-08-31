# File: app/main.py

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import auth, courses, forms, sse, uploads, users, websocket
from app.api.v2 import advanced_auth, advanced_courses
from app.core.config import settings
from app.core.logging import setup_logging
from app.exceptions.base_exceptions import BaseAppException
from app.middleware.cors_middleware import setup_cors
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.request_timer import RequestTimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    setup_logging()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting up...")
    print(f"📊 Environment: {settings.ENVIRONMENT}")
    print(f"🔧 Debug mode: {settings.DEBUG}")
    
    yield
    
    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down...")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Comprehensive FastAPI learning hub with advanced features",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Add middleware
    setup_middleware(app)
    
    # Add routers
    setup_routers(app)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI) -> None:
    """Configure application middleware."""
    
    # Session middleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.JWT_SECRET_KEY
    )
    
    # Custom middleware
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    # CORS middleware
    setup_cors(app)


def setup_routers(app: FastAPI) -> None:
    """Configure API routers."""
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": f"Welcome to {settings.APP_NAME}!",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health"
        }
    
    # API v1 routes
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    app.include_router(
        users.router,
        prefix="/api/v1/users",
        tags=["Users"]
    )
    app.include_router(
        courses.router,
        prefix="/api/v1/courses",
        tags=["Courses"]
    )
    app.include_router(
        uploads.router,
        prefix="/api/v1/uploads",
        tags=["File Uploads"]
    )
    app.include_router(
        forms.router,
        prefix="/api/v1/forms",
        tags=["Form Handling"]
    )
    app.include_router(
        websocket.router,
        prefix="/api/v1/ws",
        tags=["WebSocket"]
    )
    app.include_router(
        sse.router,
        prefix="/api/v1/sse",
        tags=["Server-Sent Events"]
    )
    
    # API v2 routes (Advanced features)
    app.include_router(
        advanced_auth.router,
        prefix="/api/v2/auth",
        tags=["Advanced Authentication"]
    )
    app.include_router(
        advanced_courses.router,
        prefix="/api/v2/courses",
        tags=["Advanced Courses"]
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""
    
    @app.exception_handler(BaseAppException)
    async def custom_exception_handler(request: Request, exc: BaseAppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        )
    
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "error": "NOT_FOUND",
                "message": "The requested resource was not found",
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc):
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        )


# Create the application instance
app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )