# File: app/exceptions/base_exceptions.py

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class BaseAppException(HTTPException):
    """Base exception class for application-specific errors."""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail=message,
            headers=headers
        )


class BadRequestException(BaseAppException):
    """Exception for 400 Bad Request errors."""
    
    def __init__(
        self,
        message: str = "Bad request",
        error_code: str = "BAD_REQUEST",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )


class UnauthorizedException(BaseAppException):
    """Exception for 401 Unauthorized errors."""
    
    def __init__(
        self,
        message: str = "Unauthorized",
        error_code: str = "UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message,
            details=details,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenException(BaseAppException):
    """Exception for 403 Forbidden errors."""
    
    def __init__(
        self,
        message: str = "Forbidden",
        error_code: str = "FORBIDDEN",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            message=message,
            details=details
        )


class NotFoundException(BaseAppException):
    """Exception for 404 Not Found errors."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=message,
            details=details
        )


class ConflictException(BaseAppException):
    """Exception for 409 Conflict errors."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        error_code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            message=message,
            details=details
        )


class UnprocessableEntityException(BaseAppException):
    """Exception for 422 Unprocessable Entity errors."""
    
    def __init__(
        self,
        message: str = "Unprocessable entity",
        error_code: str = "UNPROCESSABLE_ENTITY",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=error_code,
            message=message,
            details=details
        )


class RateLimitException(BaseAppException):
    """Exception for 429 Too Many Requests errors."""
    
    def __init__(
        self,
        message: str = "Too many requests",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=error_code,
            message=message,
            details=details,
            headers=headers
        )


class InternalServerException(BaseAppException):
    """Exception for 500 Internal Server Error."""
    
    def __init__(
        self,
        message: str = "Internal server error",
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            details=details
        )


class ServiceUnavailableException(BaseAppException):
    """Exception for 503 Service Unavailable errors."""
    
    def __init__(
        self,
        message: str = "Service unavailable",
        error_code: str = "SERVICE_UNAVAILABLE",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=error_code,
            message=message,
            details=details,
            headers=headers
        )


class DatabaseException(InternalServerException):
    """Exception for database-related errors."""
    
    def __init__(
        self,
        message: str = "Database error occurred",
        error_code: str = "DATABASE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class CacheException(InternalServerException):
    """Exception for cache-related errors."""
    
    def __init__(
        self,
        message: str = "Cache error occurred",
        error_code: str = "CACHE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class ExternalServiceException(InternalServerException):
    """Exception for external service errors."""
    
    def __init__(
        self,
        service_name: str,
        message: str = "External service error",
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        details.update({
            "resource": resource,
            "limit": limit,
            "current": current
        })
        
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class DuplicateResourceException(ConflictException):
    """Exception for duplicate resource creation attempts."""
    
    def __init__(
        self,
        resource_type: str,
        identifier: str,
        error_code: str = "DUPLICATE_RESOURCE",
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource_type} with identifier '{identifier}' already exists"
        
        if details is None:
            details = {}
        
        details.update({
            "resource_type": resource_type,
            "identifier": identifier
        })
        
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class ConfigurationException(InternalServerException):
    """Exception for configuration-related errors."""
    
    def __init__(
        self,
        setting: str,
        message: str = "Configuration error",
        error_code: str = "CONFIGURATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        details["setting"] = setting
        
        super().__init__(
            message=f"Configuration error for '{setting}': {message}",
            error_code=error_code,
            details=details
        )
            details = {}
        details["service"] = service_name
        
        super().__init__(
            message=f"{service_name}: {message}",
            error_code=error_code,
            details=details
        )


class BusinessLogicException(BadRequestException):
    """Exception for business logic violations."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "BUSINESS_LOGIC_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details
        )


class ResourceLimitException(BadRequestException):
    """Exception for resource limit violations."""
    
    def __init__(
        self,
        resource: str,
        limit: int,
        current: int,
        error_code: str = "RESOURCE_LIMIT_EXCEEDED",
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource} limit exceeded. Current: {current}, Limit: {limit}"
        
        if details is None: