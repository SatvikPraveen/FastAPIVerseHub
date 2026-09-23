# File: app/core/logging.py
"""Structured logging built on structlog.

* Every log line carries the current ``request_id`` (bound per request by the
  request-context middleware via contextvars), so a single grep on a
  correlation id reconstructs a request across services.
* Output is human-readable in development and JSON in production/staging,
  switchable with ``LOG_FORMAT``.
* Third-party libraries that log through stdlib ``logging`` are routed
  through the same processors, so their lines get the same shape.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_NOISY_LOGGERS = ("uvicorn.access", "sqlalchemy.engine", "redis", "httpx", "httpcore")


def _add_request_id(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    request_id = request_id_var.get()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    return event_dict


def _shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]


def _renderer() -> Any:
    if settings.LOG_FORMAT == "json" or settings.ENVIRONMENT in {"staging", "production"}:
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())


def configure_structlog() -> None:
    """Route structlog through stdlib ``logging``.

    Called at import time so that loggers obtained before :func:`setup_logging`
    runs (module-level ``logger = get_logger(__name__)``) already emit through
    stdlib handlers.  That is also what lets ``caplog`` capture them in tests,
    where the application lifespan never runs.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_shared_processors(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def setup_logging() -> None:
    """Configure structlog and stdlib logging handlers. Safe to call more than once."""
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    shared = _shared_processors()

    configure_structlog()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _renderer(),
        ],
    )

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if settings.LOG_FILE:
        settings.create_log_path()
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_SIZE,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(level)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    # Our own access log replaces uvicorn's
    logging.getLogger("uvicorn.access").propagate = False

    structlog.get_logger(__name__).info(
        "logging configured", level=settings.LOG_LEVEL, format=settings.LOG_FORMAT
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name``."""
    return structlog.stdlib.get_logger(name)


def bind_request_context(**values: Any) -> None:
    """Attach key/value pairs to every log line emitted for the current request."""
    structlog.contextvars.bind_contextvars(**values)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()


configure_structlog()
