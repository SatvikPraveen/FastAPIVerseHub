# File: app/middleware/cors_middleware.py
"""CORS configuration.

Starlette's ``CORSMiddleware`` is used as-is; this module only translates
settings into its arguments.  It is registered last in ``setup_middleware``
so it is the outermost layer and answers preflight requests before rate
limiting or authentication run.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

EXPOSED_HEADERS = [
    "X-Process-Time",
    "X-Request-ID",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "Retry-After",
]


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the FastAPI application."""
    allow_headers = (
        ["*"]
        if settings.CORS_HEADERS.strip() == "*"
        else [h.strip() for h in settings.CORS_HEADERS.split(",") if h.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.cors_methods_list,
        allow_headers=allow_headers,
        expose_headers=EXPOSED_HEADERS,
        max_age=3600,  # cache preflight responses for an hour
    )
