# File: app/core/logging.py

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Any, Dict

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, 'extra_data'):
            log_entry["extra_data"] = record.extra_data
        
        return json.dumps(log_entry, ensure_ascii=False)


class RequestLogger:
    """Logger for HTTP requests with correlation IDs."""
    
    def __init__(self):
        self.logger = logging.getLogger("fastapi.requests")
    
    def log_request(
        self, 
        method: str, 
        url: str, 
        status_code: int,
        duration: float,
        request_id: str = None,
        user_id: int = None,
        extra_data: Dict[str, Any] = None
    ) -> None:
        """Log HTTP request details."""
        message = f"{method} {url} - {status_code} ({duration:.3f}s)"
        
        extra = {
            "request_id": request_id,
            "user_id": user_id,
            "extra_data": extra_data or {}
        }
        
        # Choose log level based on status code
        if status_code >= 500:
            self.logger.error(message, extra=extra)
        elif status_code >= 400:
            self.logger.warning(message, extra=extra)
        else:
            self.logger.info(message, extra=extra)


def setup_logging() -> None:
    """Configure application logging."""
    
    # Create logs directory
    settings.create_log_path()
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    if settings.ENVIRONMENT == "development":
        # Simple format for development
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # JSON format for production
        console_formatter = JSONFormatter()
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    
    # FastAPI logger
    fastapi_logger = logging.getLogger("fastapi")
    fastapi_logger.setLevel(logging.INFO)
    
    # Uvicorn logger
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []  # Remove default handler
    
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.handlers = []  # Remove default handler
    
    # SQLAlchemy logger (only show warnings and errors)
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)
    
    # Redis logger
    redis_logger = logging.getLogger("redis")
    redis_logger.setLevel(logging.WARNING)
    
    # Celery logger
    celery_logger = logging.getLogger("celery")
    celery_logger.setLevel(logging.INFO)
    
    logging.info(f"Logging configured - Level: {settings.LOG_LEVEL}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: str = None,
    user_id: int = None,
    **kwargs
) -> None:
    """Log message with request context."""
    extra = {
        "request_id": request_id,
        "user_id": user_id,
        "extra_data": kwargs
    }
    logger.log(level, message, extra=extra)


# Global request logger instance
request_logger = RequestLogger()