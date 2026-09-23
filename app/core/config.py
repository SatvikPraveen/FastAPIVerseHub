# File: app/core/config.py
"""Application settings.

Values come from environment variables (or a ``.env`` file).  Validation
runs once at import time so misconfiguration fails fast at startup rather
than on the first request that happens to touch the broken setting.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import EmailStr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

INSECURE_SECRET_MARKERS = ("change-me", "changeme", "secret", "password", "example")
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings and configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FastAPIVerseHub"
    FRONTEND_URL: str = "http://localhost:3000"  # base for links in emails
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: Environment = "development"

    # Database
    DATABASE_URL: str = ""
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "fastapi_db"
    DATABASE_USER: str = "fastapi_user"
    DATABASE_PASSWORD: str = "fastapi_pass"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = ""
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # JWT & Security
    JWT_SECRET_KEY: SecretStr = SecretStr("change-me-in-production-use-a-long-random-string")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OAuth2 (Optional)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: SecretStr | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: SecretStr | None = None

    # Email
    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = 587
    EMAIL_USER: str | None = None
    EMAIL_PASSWORD: SecretStr | None = None
    EMAIL_FROM: EmailStr = "noreply@fastapiversehub.com"
    EMAIL_USE_TLS: bool = True

    # File Upload
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_PATH: str = "./uploads"
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,pdf,txt,docx,xlsx"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100  # per 10-second window

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS,PATCH"
    CORS_HEADERS: str = "*"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["console", "json"] = "console"
    LOG_FILE: str | None = None
    LOG_MAX_SIZE: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    SLOW_REQUEST_THRESHOLD_SECONDS: float = 1.0

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    HEALTH_CHECK_TIMEOUT: float = 5.0

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @model_validator(mode="before")
    @classmethod
    def build_urls(cls, values: Any) -> Any:
        """Build DATABASE_URL and REDIS_URL from components if not explicitly set."""
        if not isinstance(values, dict):
            return values

        if not values.get("DATABASE_URL"):
            user = values.get("DATABASE_USER", "fastapi_user")
            password = values.get("DATABASE_PASSWORD", "fastapi_pass")
            host = values.get("DATABASE_HOST", "localhost")
            port = values.get("DATABASE_PORT", 5432)
            database = values.get("DATABASE_NAME", "fastapi_db")
            values["DATABASE_URL"] = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        if not values.get("REDIS_URL"):
            host = values.get("REDIS_HOST", "localhost")
            port = values.get("REDIS_PORT", 6379)
            db = values.get("REDIS_DB", 0)
            values["REDIS_URL"] = f"redis://{host}:{port}/{db}"

        return values

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unsupported LOG_LEVEL {value!r}")
        return level

    @model_validator(mode="after")
    def enforce_production_safety(self) -> Settings:
        """Refuse to start in production with development-grade settings."""
        if self.ENVIRONMENT != "production":
            return self

        problems: list[str] = []
        secret = self.JWT_SECRET_KEY.get_secret_value()
        if len(secret) < MIN_SECRET_LENGTH:
            problems.append(f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters")
        if any(marker in secret.lower() for marker in INSECURE_SECRET_MARKERS):
            problems.append("JWT_SECRET_KEY looks like a placeholder value")
        if self.DEBUG:
            problems.append("DEBUG must be false in production")
        if "*" in self.cors_origins_list:
            problems.append("CORS_ORIGINS must not contain '*' in production")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy URL with an async driver, whatever form the env provided."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("sqlite://") and "+aiosqlite" not in url:
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cors_methods_list(self) -> list[str]:
        return [method.strip() for method in self.CORS_METHODS.split(",") if method.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()]

    def create_upload_path(self) -> None:
        os.makedirs(self.UPLOAD_PATH, exist_ok=True)

    def create_log_path(self) -> None:
        if self.LOG_FILE:
            log_dir = os.path.dirname(self.LOG_FILE)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
