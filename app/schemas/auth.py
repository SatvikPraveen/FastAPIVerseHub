# File: app/schemas/auth.py

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr, validator


class LoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str
    remember_me: bool = False


class UserRegistration(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str
    confirm_password: str
    full_name: Optional[str] = None
    accept_terms: bool = True
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('accept_terms')
    def terms_must_be_accepted(cls, v):
        if not v:
            raise ValueError('Terms and conditions must be accepted')
        return v


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: Optional[Dict[str, Any]] = None
    requires_mfa: Optional[bool] = None
    partial_token: Optional[str] = None
    message: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class TokenVerificationResponse(BaseModel):
    """Schema for token verification response."""
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    token_type: Optional[str] = None
    expires_at: Optional[int] = None
    scopes: Optional[List[str]] = None


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str
    confirm_new_password: str
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str
    confirm_new_password: str
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('New passwords do not match')
        return v
    
    @validator('new_password')
    def validate_new_password(cls, v, values, **kwargs):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
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
    backup_codes: List[str]
    manual_entry_key: str
    message: str


class MFAVerificationRequest(BaseModel):
    """Schema for MFA verification request."""
    token: Optional[str] = None
    backup_code: Optional[str] = None
    
    @validator('token', 'backup_code')
    def at_least_one_required(cls, v, values):
        if not v and not values.get('backup_code') and not values.get('token'):
            raise ValueError('Either token or backup_code must be provided')
        return v


class SocialAuthRequest(BaseModel):
    """Schema for social authentication request."""
    provider: str
    access_token: str
    id_token: Optional[str] = None
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ['google', 'github', 'linkedin', 'facebook']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {", ".join(allowed_providers)}')
        return v


class SocialAuthResponse(BaseModel):
    """Schema for social authentication response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    is_new_user: bool


class DeviceRegistrationRequest(BaseModel):
    """Schema for device registration request."""
    device_name: str
    device_type: str
    device_fingerprint: str
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    
    @validator('device_type')
    def validate_device_type(cls, v):
        allowed_types = ['mobile', 'tablet', 'desktop', 'tv', 'watch']
        if v not in allowed_types:
            raise ValueError(f'Device type must be one of: {", ".join(allowed_types)}')
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
    os_name: Optional[str] = None
    browser_name: Optional[str] = None
    last_used_at: Optional[datetime] = None
    is_current: bool = False
    created_at: datetime


class MagicLinkRequest(BaseModel):
    """Schema for magic link authentication request."""
    email: EmailStr
    redirect_url: Optional[str] = None


class MagicLinkVerification(BaseModel):
    """Schema for magic link verification."""
    token: str


class SessionInfo(BaseModel):
    """Schema for session information."""
    session_id: str
    device_info: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    last_activity: Optional[datetime] = None
    is_current: bool = False
    created_at: datetime


class APIKeyRequest(BaseModel):
    """Schema for API key creation request."""
    name: str
    description: Optional[str] = None
    scopes: List[str]
    expires_at: Optional[datetime] = None
    rate_limit_per_hour: Optional[int] = 1000
    allowed_ips: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    """Schema for API key response."""
    id: int
    name: str
    key_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool


class LoginAttempt(BaseModel):
    """Schema for login attempt tracking."""
    email: EmailStr
    ip_address: str
    user_agent: str
    success: bool
    failure_reason: Optional[str] = None
    timestamp: datetime
    location: Optional[str] = None


class SecurityEvent(BaseModel):
    """Schema for security events."""
    event_type: str
    description: str
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    severity: str = "low"
    timestamp: datetime


class AccountLockout(BaseModel):
    """Schema for account lockout information."""
    user_id: int
    reason: str
    locked_at: datetime
    unlock_at: Optional[datetime] = None
    attempt_count: int
    is_permanent: bool = False


class RolePermission(BaseModel):
    """Schema for role permissions."""
    role: str
    permissions: List[str]
    description: Optional[str] = None


class UserRole(BaseModel):
    """Schema for user roles."""
    user_id: int
    role: str
    granted_by: int
    granted_at: datetime
    expires_at: Optional[datetime] = None