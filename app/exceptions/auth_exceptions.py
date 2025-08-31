# File: app/exceptions/auth_exceptions.py

from typing import Any, Dict, Optional
from app.exceptions.base_exceptions import UnauthorizedException, ForbiddenException, BadRequestException


class InvalidCredentialsException(UnauthorizedException):
    """Exception for invalid login credentials."""
    
    def __init__(
        self,
        message: str = "Invalid email or password",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
            details=details
        )


class TokenExpiredException(UnauthorizedException):
    """Exception for expired JWT tokens."""
    
    def __init__(
        self,
        token_type: str = "access",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"The {token_type} token has expired"
        
        if details is None:
            details = {}
        details["token_type"] = token_type
        
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
            details=details
        )


class InvalidTokenException(UnauthorizedException):
    """Exception for invalid or malformed tokens."""
    
    def __init__(
        self,
        message: str = "Invalid or malformed token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_TOKEN",
            details=details
        )


class TokenRevokedException(UnauthorizedException):
    """Exception for revoked tokens."""
    
    def __init__(
        self,
        message: str = "Token has been revoked",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="TOKEN_REVOKED",
            details=details
        )


class MFARequiredException(UnauthorizedException):
    """Exception when MFA verification is required."""
    
    def __init__(
        self,
        message: str = "Multi-factor authentication required",
        partial_token: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        if partial_token:
            details["partial_token"] = partial_token
            details["next_step"] = "mfa_verification"
        
        super().__init__(
            message=message,
            error_code="MFA_REQUIRED",
            details=details
        )


class InvalidMFATokenException(UnauthorizedException):
    """Exception for invalid MFA tokens."""
    
    def __init__(
        self,
        message: str = "Invalid MFA token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_MFA_TOKEN",
            details=details
        )


class MFANotSetupException(BadRequestException):
    """Exception when MFA is not set up but required."""
    
    def __init__(
        self,
        message: str = "MFA is not set up for this account",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="MFA_NOT_SETUP",
            details=details
        )


class AccountLockedException(ForbiddenException):
    """Exception for locked user accounts."""
    
    def __init__(
        self,
        message: str = "Account is locked due to security reasons",
        unlock_time: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        if unlock_time:
            details["unlock_time"] = unlock_time
            message = f"{message}. Account will be unlocked at {unlock_time}"
        
        super().__init__(
            message=message,
            error_code="ACCOUNT_LOCKED",
            details=details
        )


class AccountDisabledException(ForbiddenException):
    """Exception for disabled user accounts."""
    
    def __init__(
        self,
        message: str = "Account has been disabled",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="ACCOUNT_DISABLED",
            details=details
        )


class AccountNotVerifiedException(ForbiddenException):
    """Exception for unverified user accounts."""
    
    def __init__(
        self,
        message: str = "Account email is not verified",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="ACCOUNT_NOT_VERIFIED",
            details=details
        )


class InsufficientPermissionsException(ForbiddenException):
    """Exception for insufficient permissions."""
    
    def __init__(
        self,
        required_permission: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"Insufficient permissions. Required: {required_permission}"
        
        if details is None:
            details = {}
        details["required_permission"] = required_permission
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            details=details
        )


class PasswordTooWeakException(BadRequestException):
    """Exception for weak passwords."""
    
    def __init__(
        self,
        requirements: list,
        message: str = "Password does not meet security requirements",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["requirements"] = requirements
        
        super().__init__(
            message=message,
            error_code="PASSWORD_TOO_WEAK",
            details=details
        )


class PasswordRecentlyUsedException(BadRequestException):
    """Exception for recently used passwords."""
    
    def __init__(
        self,
        message: str = "Password was recently used. Please choose a different password",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="PASSWORD_RECENTLY_USED",
            details=details
        )


class TooManyLoginAttemptsException(ForbiddenException):
    """Exception for too many failed login attempts."""
    
    def __init__(
        self,
        retry_after: int,
        message: str = "Too many failed login attempts",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["retry_after"] = retry_after
        
        message = f"{message}. Try again after {retry_after} seconds"
        
        super().__init__(
            message=message,
            error_code="TOO_MANY_LOGIN_ATTEMPTS",
            details=details
        )


class InvalidResetTokenException(BadRequestException):
    """Exception for invalid password reset tokens."""
    
    def __init__(
        self,
        message: str = "Invalid or expired password reset token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_RESET_TOKEN",
            details=details
        )


class SocialAuthException(UnauthorizedException):
    """Exception for social authentication errors."""
    
    def __init__(
        self,
        provider: str,
        message: str = "Social authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["provider"] = provider
        
        super().__init__(
            message=f"{provider} authentication failed: {message}",
            error_code="SOCIAL_AUTH_FAILED",
            details=details
        )


class DeviceNotTrustedException(ForbiddenException):
    """Exception for untrusted devices."""
    
    def __init__(
        self,
        message: str = "Device is not trusted for this account",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DEVICE_NOT_TRUSTED",
            details=details
        )


class SessionExpiredException(UnauthorizedException):
    """Exception for expired user sessions."""
    
    def __init__(
        self,
        message: str = "Session has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="SESSION_EXPIRED",
            details=details
        )


class InvalidAPIKeyException(UnauthorizedException):
    """Exception for invalid API keys."""
    
    def __init__(
        self,
        message: str = "Invalid API key",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_API_KEY",
            details=details
        )


class APIKeyExpiredException(UnauthorizedException):
    """Exception for expired API keys."""
    
    def __init__(
        self,
        message: str = "API key has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="API_KEY_EXPIRED",
            details=details
        )


class InsufficientScopeException(ForbiddenException):
    """Exception for insufficient API scopes."""
    
    def __init__(
        self,
        required_scopes: list,
        message: str = "Insufficient API scopes",
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        details["required_scopes"] = required_scopes
        
        super().__init__(
            message=f"{message}. Required scopes: {', '.join(required_scopes)}",
            error_code="INSUFFICIENT_SCOPE",
            details=details
        )