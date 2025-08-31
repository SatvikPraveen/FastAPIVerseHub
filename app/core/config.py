# File: app/core/config.py

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, EmailStr, validator


class Settings(BaseSettings):
    """Application settings and configuration."""
    
    # Application
    APP_NAME: str = "FastAPIVerseHub"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "fastapi_db"
    DATABASE_USER: str = "fastapi_user"
    DATABASE_PASSWORD: str = "fastapi_pass"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # JWT & Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth2 (Optional)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    
    # Email
    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = 587
    EMAIL_USER: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_FROM: EmailStr = "noreply@fastapiversehub.com"
    EMAIL_USE_TLS: bool = True
    
    # File Upload
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_PATH: str = "./uploads"
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,pdf,txt,docx,xlsx"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100
    
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
    LOG_FILE: str = "./logs/app.log"
    LOG_MAX_SIZE: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    HEALTH_CHECK_TIMEOUT: int = 5
    
    @validator("DATABASE_URL", pre=True)
    def build_database_url(cls, v: Optional[str], values: dict) -> str:
        """Build database URL from components if not provided."""
        if v:
            return v
        
        user = values.get("DATABASE_USER", "fastapi_user")
        password = values.get("DATABASE_PASSWORD", "fastapi_pass")
        host = values.get("DATABASE_HOST", "localhost")
        port = values.get("DATABASE_PORT", 5432)
        database = values.get("DATABASE_NAME", "fastapi_db")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    @validator("REDIS_URL", pre=True)
    def build_redis_url(cls, v: Optional[str], values: dict) -> str:
        """Build Redis URL from components if not provided."""
        if v:
            return v
        
        host = values.get("REDIS_HOST", "localhost")
        port = values.get("REDIS_PORT", 6379)
        db = values.get("REDIS_DB", 0)
        
        return f"redis://{host}:{port}/{db}"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def cors_methods_list(self) -> List[str]:
        """Get CORS methods as a list."""
        return [method.strip() for method in self.CORS_METHODS.split(",")]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get allowed file extensions as a list."""
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]
    
    def create_upload_path(self) -> None:
        """Create upload directory if it doesn't exist."""
        os.makedirs(self.UPLOAD_PATH, exist_ok=True)
    
    def create_log_path(self) -> None:
        """Create log directory if it doesn't exist."""
        log_dir = os.path.dirname(self.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()