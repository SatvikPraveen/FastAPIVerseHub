# File: app/main.py
"""Application factory and ASGI entry point."""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import health
from app.api.v1 import auth, courses, forms, sse, uploads, users, websocket
from app.api.v2 import advanced_auth, advanced_courses
from app.common.cache_utils import cache_manager
from app.core import metrics
from app.core.config import settings
from app.core.dependencies import engine
from app.core.logging import get_logger, setup_logging
from app.exceptions.base_exceptions import BaseAppException
from app.middleware.cors_middleware import setup_cors
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.request_timer import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start and stop shared resources.

    Anything created here lives on ``app.state`` and is closed in reverse
    order on shutdown, so a SIGTERM drains connections cleanly.
    """
    setup_logging()
    app.state.started_at = time.time()
    logger.info(
        "application starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )

    # Redis: one pool for cache, rate limiting, sessions and health checks.
    # Tests bind a fake client before startup; do not replace it.
    if cache_manager.redis_client is None:
        cache_manager.bind(
            redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=settings.HEALTH_CHECK_TIMEOUT,
            )
        )
    app.state.redis = cache_manager.redis_client
    app.state.db_engine = engine

    try:
        yield
    finally:
        logger.info("application shutting down")
        await cache_manager.close()
        await engine.dispose()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Comprehensive FastAPI learning hub with advanced features",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
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
    """Configure the middleware stack.

    Starlette wraps middleware in reverse registration order, so the *last*
    ``add_middleware`` call is the outermost layer.  Reading bottom-up:

        CORS -> request context -> gzip -> security headers -> metrics
             -> rate limit -> session -> routes
    """
    app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET_KEY.get_secret_value())
    app.add_middleware(RateLimitMiddleware)
    if settings.PROMETHEUS_ENABLED:
        app.add_middleware(metrics.PrometheusMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestContextMiddleware)
    setup_cors(app)


def setup_routers(app: FastAPI) -> None:
    """Configure API routers."""

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "message": f"Welcome to {settings.APP_NAME}!",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics" if settings.PROMETHEUS_ENABLED else None,
        }

    app.include_router(health.router)
    if settings.PROMETHEUS_ENABLED:
        app.include_router(metrics.router)

    # API v1 routes
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(courses.router, prefix="/api/v1/courses", tags=["Courses"])
    app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["File Uploads"])
    app.include_router(forms.router, prefix="/api/v1/forms", tags=["Form Handling"])
    app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])
    app.include_router(sse.router, prefix="/api/v1/sse", tags=["Server-Sent Events"])

    # API v2 routes (Advanced features)
    app.include_router(
        advanced_auth.router, prefix="/api/v2/auth", tags=["Advanced Authentication"]
    )
    app.include_router(advanced_courses.router, prefix="/api/v2/courses", tags=["Advanced Courses"])


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

    def _envelope(
        request: Request, status_code: int, error: str, message: str, details: Any = None
    ) -> JSONResponse:
        body: dict[str, Any] = {
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
        response = _envelope(
            request, exc.status_code, _error_code_for(exc.status_code), message, details
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
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
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
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


def main() -> None:
    """Console entry point (``fastapi-verse-hub``)."""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
