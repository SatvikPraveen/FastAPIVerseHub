# File: app/api/v2/advanced_auth.py

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
import pyotp
import qrcode
from io import BytesIO
import base64

from app.core.dependencies import get_current_active_user, get_db, get_redis
from app.core.security import security_manager
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


class MFASetupRequest(BaseModel):
    """Multi-factor authentication setup request."""
    password: str


class MFAVerifyRequest(BaseModel):
    """Multi-factor authentication verify request."""
    token: str
    backup_code: Optional[str] = None


class DeviceRegistrationRequest(BaseModel):
    """Device registration request."""
    device_name: str
    device_type: str
    device_fingerprint: str


class SocialAuthRequest(BaseModel):
    """Social authentication request."""
    provider: str
    access_token: str
    id_token: Optional[str] = None


class PasswordlessRequest(BaseModel):
    """Passwordless authentication request."""
    email: EmailStr
    method: str = "email"  # email or sms


class MagicLinkVerifyRequest(BaseModel):
    """Magic link verification request."""
    token: str


@router.post("/mfa/setup")
async def setup_mfa(
    request: MFASetupRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Setup multi-factor authentication."""
    auth_service = AuthService(db)
    
    # Verify password
    if not security_manager.verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password"
        )
    
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled"
        )
    
    # Generate TOTP secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    
    # Generate QR code
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="FastAPIVerseHub"
    )
    
    # Create QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_image = base64.b64encode(buffer.getvalue()).decode()
    
    # Generate backup codes
    backup_codes = [secrets.token_hex(8) for _ in range(10)]
    
    # Save MFA setup (but don't enable until verified)
    await auth_service.setup_mfa(
        user_id=current_user.id,
        secret=secret,
        backup_codes=backup_codes
    )
    
    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_image}",
        "backup_codes": backup_codes,
        "manual_entry_key": secret,
        "message": "Scan the QR code with your authenticator app and verify with a token"
    }


@router.post("/mfa/verify")
async def verify_mfa_setup(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Verify and enable MFA."""
    auth_service = AuthService(db)
    
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled"
        )
    
    # Get MFA setup data
    mfa_setup = await auth_service.get_mfa_setup(current_user.id)
    if not mfa_setup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not found. Please start setup process."
        )
    
    # Verify TOTP token
    totp = pyotp.TOTP(mfa_setup["secret"])
    if not totp.verify(request.token, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authentication code"
        )
    
    # Enable MFA
    await auth_service.enable_mfa(current_user.id, mfa_setup["secret"], mfa_setup["backup_codes"])
    
    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable")
async def disable_mfa(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Disable MFA."""
    auth_service = AuthService(db)
    
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled"
        )
    
    # Verify TOTP token or backup code
    valid = False
    if request.token:
        totp = pyotp.TOTP(current_user.mfa_secret)
        valid = totp.verify(request.token, valid_window=1)
    elif request.backup_code:
        valid = await auth_service.verify_backup_code(current_user.id, request.backup_code)
    
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authentication code or backup code"
        )
    
    await auth_service.disable_mfa(current_user.id)
    
    return {"message": "MFA disabled successfully"}


@router.post("/login/mfa", response_model=TokenResponse)
async def login_with_mfa(
    email: EmailStr,
    password: str,
    mfa_token: Optional[str] = None,
    backup_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Login with MFA verification."""
    auth_service = AuthService(db)
    
    # First verify email and password
    user = await auth_service.authenticate_user(email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # If MFA is enabled, verify second factor
    if user.mfa_enabled:
        if not mfa_token and not backup_code:
            # Return partial token for MFA verification
            partial_token = security_manager.create_access_token(
                data={"sub": str(user.id), "mfa_pending": True},
                expires_delta=timedelta(minutes=5)
            )
            return {
                "requires_mfa": True,
                "partial_token": partial_token,
                "message": "MFA verification required"
            }
        
        # Verify MFA token or backup code
        valid = False
        if mfa_token:
            totp = pyotp.TOTP(user.mfa_secret)
            valid = totp.verify(mfa_token, valid_window=1)
        elif backup_code:
            valid = await auth_service.verify_backup_code(user.id, backup_code)
        
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code"
            )
    
    # Generate tokens
    tokens = security_manager.create_token_pair(
        user_id=user.id,
        additional_data={"email": user.email, "mfa_verified": True}
    )
    
    await auth_service.update_last_login(user.id)
    
    return {
        **tokens,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "mfa_enabled": user.mfa_enabled
        }
    }


@router.post("/devices/register")
async def register_device(
    request: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Register trusted device."""
    auth_service = AuthService(db)
    
    device = await auth_service.register_device(
        user_id=current_user.id,
        device_name=request.device_name,
        device_type=request.device_type,
        device_fingerprint=request.device_fingerprint
    )
    
    return {
        "device_id": device.id,
        "device_name": device.device_name,
        "device_token": device.device_token,
        "registered_at": device.created_at
    }


@router.get("/devices")
async def list_devices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """List user's registered devices."""
    auth_service = AuthService(db)
    
    devices = await auth_service.get_user_devices(current_user.id)
    
    return {
        "devices": [
            {
                "id": device.id,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "last_used": device.last_used_at,
                "is_current": device.device_fingerprint == "current",  # You'd implement this check
                "created_at": device.created_at
            }
            for device in devices
        ]
    }


@router.delete("/devices/{device_id}")
async def revoke_device(
    device_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Revoke trusted device."""
    auth_service = AuthService(db)
    
    await auth_service.revoke_device(current_user.id, device_id)
    
    return {"message": "Device revoked successfully"}


@router.post("/social/auth")
async def social_auth(
    request: SocialAuthRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Authenticate with social provider."""
    auth_service = AuthService(db)
    
    # Verify social token and get user info
    user_info = await auth_service.verify_social_token(
        provider=request.provider,
        access_token=request.access_token,
        id_token=request.id_token
    )
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid social authentication"
        )
    
    # Get or create user
    user = await auth_service.get_or_create_social_user(
        provider=request.provider,
        social_id=user_info["id"],
        email=user_info["email"],
        full_name=user_info.get("name"),
        avatar_url=user_info.get("picture")
    )
    
    # Generate tokens
    tokens = security_manager.create_token_pair(
        user_id=user.id,
        additional_data={"email": user.email, "social_provider": request.provider}
    )
    
    return {
        **tokens,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_new_user": user.created_at > datetime.utcnow() - timedelta(minutes=1)
        }
    }


@router.post("/passwordless/request")
async def request_passwordless_auth(
    request: PasswordlessRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Request passwordless authentication."""
    auth_service = AuthService(db)
    
    user = await auth_service.get_user_by_email(request.email)
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, an authentication link has been sent"}
    
    # Generate magic link token
    magic_token = security_manager.create_access_token(
        data={"sub": str(user.id), "type": "magic_link"},
        expires_delta=timedelta(minutes=15)
    )
    
    if request.method == "email":
        # Send magic link via email
        await auth_service.send_magic_link_email(user.email, magic_token)
    elif request.method == "sms":
        # Send code via SMS (if implemented)
        await auth_service.send_magic_link_sms(user.phone, magic_token)
    
    return {"message": "Authentication link sent successfully"}


@router.post("/passwordless/verify", response_model=TokenResponse)
async def verify_magic_link(
    request: MagicLinkVerifyRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Verify magic link token."""
    try:
        payload = security_manager.verify_token(request.token)
        
        if payload.get("type") != "magic_link":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )
        
        user_id = int(payload.get("sub"))
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_id(user_id)
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user"
            )
        
        # Generate regular tokens
        tokens = security_manager.create_token_pair(
            user_id=user.id,
            additional_data={"email": user.email, "passwordless": True}
        )
        
        await auth_service.update_last_login(user.id)
        
        return {
            **tokens,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name
            }
        }
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )


@router.get("/sessions")
async def list_active_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
) -> Dict[str, Any]:
    """List user's active sessions."""
    auth_service = AuthService(db)
    
    sessions = await auth_service.get_user_sessions(current_user.id, redis)
    
    return {
        "sessions": [
            {
                "session_id": session["session_id"],
                "device_info": session.get("device_info"),
                "ip_address": session.get("ip_address"),
                "last_activity": session.get("last_activity"),
                "is_current": session.get("is_current", False)
            }
            for session in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    redis = Depends(get_redis)
) -> Dict[str, str]:
    """Revoke specific session."""
    auth_service = AuthService()
    
    await auth_service.revoke_session(current_user.id, session_id, redis)
    
    return {"message": "Session revoked successfully"}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_active_user),
    redis = Depends(get_redis)
) -> Dict[str, str]:
    """Revoke all user sessions except current."""
    auth_service = AuthService()
    
    revoked_count = await auth_service.revoke_all_sessions(current_user.id, redis)
    
    return {"message": f"Revoked {revoked_count} sessions"}