# File: app/main.py

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import auth, courses, forms, sse, uploads, users, websocket
from app.api.v2 import advanced_auth, advanced_courses
from app.core.config import settings
from app.core.logging import setup_logging
from app.exceptions.base_exceptions import BaseAppException
from app.middleware.cors_middleware import setup_cors
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.request_timer import RequestTimingMiddleware

logger = logging.getLogger(__name__)


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


_STATUS_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_code_for(status_code: int) -> str:
    return _STATUS_ERROR_CODES.get(status_code, f"HTTP_{status_code}")


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers.

    Every error response shares one envelope::

        {"error": "<MACHINE_CODE>", "message": "<human text>", "details": {...},
         "request_id": "<correlation id>"}

    so clients can branch on ``error`` without parsing prose.
    """

    def _envelope(request: Request, status_code: int, error: str, message: str,
                  details: Any = None) -> JSONResponse:
        body: Dict[str, Any] = {
            "error": error,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
        }
        return JSONResponse(status_code=status_code, content=body)

    @app.exception_handler(BaseAppException)
    async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
        response = _envelope(request, exc.status_code, exc.error_code, exc.message, exc.details)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            message = str(detail.get("message") or detail.get("detail") or "Request failed")
            details = detail
        else:
            message = str(detail) if detail else "Request failed"
            details = {}
        if exc.status_code == 404 and not exc.detail:
            message = "The requested resource was not found"
            details = {"path": request.url.path}
        response = _envelope(request, exc.status_code, _error_code_for(exc.status_code), message, details)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", ()) if loc != "body"),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return _envelope(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return _envelope(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred",
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