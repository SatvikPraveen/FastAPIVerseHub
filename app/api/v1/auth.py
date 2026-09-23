# File: app/api/v1/auth.py

from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_redis
from app.core.security import security_manager
from app.core.time import utcnow
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserRegistration,
)
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegistration, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Register a new user."""
    auth_service = AuthService(db)

    # Check if user already exists
    existing_user = await auth_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    user = await auth_service.create_user(user_data)

    # Generate tokens
    tokens = security_manager.create_token_pair(
        user_id=user.id, additional_data={"email": user.email, "is_superuser": user.is_superuser}
    )

    return {
        **tokens,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
        },
    }


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Authenticate user and return tokens."""
    auth_service = AuthService(db)

    # Authenticate user
    user = await auth_service.authenticate_user(
        email=login_data.email, password=login_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # Generate tokens
    tokens = security_manager.create_token_pair(
        user_id=user.id, additional_data={"email": user.email, "is_superuser": user.is_superuser}
    )

    # Update last login
    await auth_service.update_last_login(user.id)

    return {
        **tokens,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
        },
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshTokenRequest) -> dict[str, Any]:
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = security_manager.verify_refresh_token(refresh_data.refresh_token)
        user_id = int(payload.get("sub"))

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Create new access token
        new_access_token = security_manager.create_access_token(
            data={
                "sub": str(user_id),
                "email": payload.get("email"),
                "is_superuser": payload.get("is_superuser", False),
            }
        )

        return {
            "access_token": new_access_token,
            "refresh_token": refresh_data.refresh_token,
            "token_type": "bearer",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> dict[str, str]:
    """Logout user — blacklist the current access token's JTI in Redis."""
    try:
        payload = security_manager.verify_access_token(credentials.credentials)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            ttl = int(exp - utcnow().timestamp())
            if ttl > 0:
                await redis_client.setex(f"blacklist:jti:{jti}", ttl, "1")
    except Exception:
        pass  # Even if blacklisting fails, proceed with logout response
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Get current user information."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login_at": current_user.last_login_at,
    }


@router.post("/verify-token")
async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Verify if token is valid."""
    try:
        payload = security_manager.verify_access_token(credentials.credentials)

        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "token_type": payload.get("type"),
            "expires_at": payload.get("exp"),
        }

    except HTTPException:
        return {"valid": False}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Change user password."""
    auth_service = AuthService(db)

    # Verify current password
    if not security_manager.verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    # Update password
    await auth_service.change_password(current_user.id, request.new_password)

    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Request password reset."""
    auth_service = AuthService(db)

    # Check if user exists
    user = await auth_service.get_user_by_email(request.email)
    if not user:
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate a dedicated password_reset token (type != "access")
    security_manager.create_password_reset_token(user_id=user.id)

    # TODO: Send email with reset link
    # await email_service.send_password_reset_email(user.email, reset_token)

    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Reset password using reset token."""
    token, new_password = request.token, request.new_password
    try:
        # Verify reset token (signature + expiry)
        payload = security_manager.verify_token(token)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
        ) from exc

    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

    try:
        user_id = int(payload.get("sub"))
        auth_service = AuthService(db)

        # Reset password
        await auth_service.change_password(user_id, new_password)

        return {"message": "Password reset successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
        ) from exc
