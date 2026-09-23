# File: app/api/v1/auth.py

from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.email_utils import EmailService
from app.core.dependencies import get_client_ip, get_current_user, get_db, get_redis, get_user_agent
from app.core.logging import get_logger
from app.core.security import security_manager
from app.core.time import utcnow
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserRegistration,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

router = APIRouter()
security = HTTPBearer()
logger = get_logger(__name__)


def _public_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegistration,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new user and start a session.

    The welcome email is sent after the response: SMTP latency or an outage
    must not slow down or fail registration.
    """
    auth_service = AuthService(db)

    if await auth_service.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    user = await auth_service.create_user(user_data)
    background_tasks.add_task(EmailService().send_welcome_email, user.email, user.full_name)

    tokens = await TokenService(db).issue_pair(
        user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
    )
    return {**tokens, "user": _public_user(user)}


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Authenticate user and return an access/refresh token pair."""
    auth_service = AuthService(db)

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

    tokens = await TokenService(db).issue_pair(
        user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
    )
    await auth_service.update_last_login(user.id)
    return {**tokens, "user": _public_user(user)}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Rotate a refresh token.

    The presented token is invalidated and a new pair is returned. Presenting
    a token that was already rotated revokes the whole session family.
    """
    return await TokenService(db).rotate(
        refresh_data.refresh_token,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    body: LogoutRequest | None = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Log out of the current session.

    The access token's ``jti`` is blacklisted until it expires; if the client
    sends its refresh token it is revoked too, so the session cannot be resumed.
    """
    revoked_refresh = False
    try:
        payload = security_manager.verify_access_token(credentials.credentials)
        jti, exp = payload.get("jti"), payload.get("exp")
        if jti and exp:
            ttl = int(exp - utcnow().timestamp())
            if ttl > 0:
                await redis_client.set(f"blacklist:jti:{jti}", "1", ex=ttl)
    except Exception:
        logger.warning("could not blacklist access token on logout")

    if body and body.refresh_token:
        revoked_refresh = await TokenService(db).revoke_refresh_token(
            body.refresh_token, current_user.id
        )
    return {"message": "Successfully logged out", "refresh_token_revoked": revoked_refresh}


@router.post("/logout-all")
async def logout_everywhere(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Revoke every refresh token the user holds (all devices)."""
    revoked = await TokenService(db).revoke_all_for_user(current_user.id)
    return {"message": f"Revoked {revoked} sessions", "revoked_sessions": revoked}


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
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Request a password reset link.

    The response is identical whether or not the address exists, and the
    email goes out after the response so timing does not reveal it either.
    """
    user = await AuthService(db).get_user_by_email(request.email)
    if user and user.is_active:
        reset_token = security_manager.create_password_reset_token(user_id=user.id)
        background_tasks.add_task(
            EmailService().send_password_reset_email, user.email, reset_token, user.full_name
        )
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
        user_id = security_manager.subject_id(payload)
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
