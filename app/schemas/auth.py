# File: app/schemas/auth.py

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    """Schema for user login request."""

    email: EmailStr
    password: str
    remember_me: bool = False


class UserRegistration(BaseModel):
    """Schema for user registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    confirm_password: str
    full_name: str | None = None
    accept_terms: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("accept_terms")
    @classmethod
    def terms_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Terms and conditions must be accepted")
        return v


class TokenResponse(BaseModel):
    """Schema for authentication token response.

    ``access_token`` is ``None`` only for MFA-pending responses, which carry
    a ``partial_token`` instead.
    """

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user: dict[str, Any] | None = None
    requires_mfa: bool | None = None
    partial_token: str | None = None
    message: str | None = None


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Optional logout body: include the refresh token to revoke the session."""

    refresh_token: str | None = None


class TokenVerificationResponse(BaseModel):
    """Schema for token verification response."""

    valid: bool
    user_id: str | None = None
    email: str | None = None
    token_type: str | None = None
    expires_at: int | None = None
    scopes: list[str] | None = None


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=72)
    confirm_new_password: str | None = None

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str | None, info) -> str | None:
        if v is not None and "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password.

    ``confirm_new_password`` is optional: API clients that already confirm
    client-side may omit it, but when present it must match.
    """

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=72)
    confirm_new_password: str | None = None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str, info) -> str:
        if "current_password" in info.data and v == info.data["current_password"]:
            raise ValueError("New password must be different from current password")
        return v

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str | None, info) -> str | None:
        if v is not None and "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return v


class EmailVerificationRequest(BaseModel):
    """Schema for email verification request."""

    email: EmailStr


class EmailVerificationConfirm(BaseModel):
    """Schema for email verification confirmation."""

    token: str


class MFASetupResponse(BaseModel):
    """Schema for MFA setup response."""

    secret: str
    qr_code: str
    backup_codes: list[str]
    manual_entry_key: str
    message: str


class MFAVerificationRequest(BaseModel):
    """Schema for MFA verification request."""

    token: str | None = None
    backup_code: str | None = None

    @model_validator(mode="after")
    def at_least_one_required(self) -> "MFAVerificationRequest":
        if not self.token and not self.backup_code:
            raise ValueError("Either token or backup_code must be provided")
        return self


class SocialAuthRequest(BaseModel):
    """Schema for social authentication request."""

    provider: str
    access_token: str
    id_token: str | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed_providers = ["google", "github", "linkedin", "facebook"]
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {', '.join(allowed_providers)}")
        return v


class SocialAuthResponse(BaseModel):
    """Schema for social authentication response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict[str, Any]
    is_new_user: bool


class DeviceRegistrationRequest(BaseModel):
    """Schema for device registration request."""

    device_name: str
    device_type: str
    device_fingerprint: str
    os_name: str | None = None
    os_version: str | None = None
    browser_name: str | None = None
    browser_version: str | None = None

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        allowed_types = ["mobile", "tablet", "desktop", "tv", "watch"]
        if v not in allowed_types:
            raise ValueError(f"Device type must be one of: {', '.join(allowed_types)}")
        return v


class DeviceRegistrationResponse(BaseModel):
    """Schema for device registration response."""

    device_id: int
    device_name: str
    device_token: str
    is_trusted: bool = False
    registered_at: datetime


class TrustedDevice(BaseModel):
    """Schema for trusted device information."""

    id: int
    device_name: str
    device_type: str
    os_name: str | None = None
    browser_name: str | None = None
    last_used_at: datetime | None = None
    is_current: bool = False
    created_at: datetime


class MagicLinkRequest(BaseModel):
    """Schema for magic link authentication request."""

    email: EmailStr
    redirect_url: str | None = None


class MagicLinkVerification(BaseModel):
    """Schema for magic link verification."""

    token: str


class SessionInfo(BaseModel):
    """Schema for session information."""

    session_id: str
    device_info: dict[str, Any] | None = None
    ip_address: str | None = None
    location: str | None = None
    last_activity: datetime | None = None
    is_current: bool = False
    created_at: datetime


class APIKeyRequest(BaseModel):
    """Schema for API key creation request."""

    name: str
    description: str | None = None
    scopes: list[str]
    expires_at: datetime | None = None
    rate_limit_per_hour: int | None = 1000
    allowed_ips: list[str] | None = None


class APIKeyResponse(BaseModel):
    """Schema for API key response."""

    id: int
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool


class LoginAttempt(BaseModel):
    """Schema for login attempt tracking."""

    email: EmailStr
    ip_address: str
    user_agent: str
    success: bool
    failure_reason: str | None = None
    timestamp: datetime
    location: str | None = None


class SecurityEvent(BaseModel):
    """Schema for security events."""

    event_type: str
    description: str
    user_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] | None = None
    severity: str = "low"
    timestamp: datetime


class AccountLockout(BaseModel):
    """Schema for account lockout information."""

    user_id: int
    reason: str
    locked_at: datetime
    unlock_at: datetime | None = None
    attempt_count: int
    is_permanent: bool = False


class RolePermission(BaseModel):
    """Schema for role permissions."""

    role: str
    permissions: list[str]
    description: str | None = None


class UserRole(BaseModel):
    """Schema for user roles."""

    user_id: int
    role: str
    granted_by: int
    granted_at: datetime
    expires_at: datetime | None = None
