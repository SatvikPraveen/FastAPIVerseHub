import json
import secrets
from datetime import timedelta
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.email_utils import EmailService
from app.core.security import security_manager
from app.core.time import utcnow
from app.models.user import DeviceRegistration, User, UserSession
from app.schemas.auth import UserRegistration

MFA_SETUP_TTL_SECONDS = 300  # 5 minutes


class AuthService:
    """Authentication service for user management."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis | None = None):
        self.db = db
        self.redis = redis
        self.email_service = EmailService()

    async def create_user(self, user_data: UserRegistration) -> User:
        """Create a new user account."""
        hashed_password = security_manager.get_password_hash(user_data.password)

        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,
            is_verified=False,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # Send welcome email
        await self.email_service.send_welcome_email(user.email, user.full_name)

        return user

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not security_manager.verify_password(password, user.hashed_password):
            return None

        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(
                last_login_at=utcnow(),
                last_activity_at=utcnow(),
                login_count=User.login_count + 1,
            )
        )
        await self.db.execute(query)
        await self.db.commit()

    async def change_password(self, user_id: int, new_password: str) -> None:
        """Change user's password."""
        hashed_password = security_manager.get_password_hash(new_password)

        query = update(User).where(User.id == user_id).values(hashed_password=hashed_password)
        await self.db.execute(query)
        await self.db.commit()

    async def setup_mfa(self, user_id: int, secret: str, backup_codes: list[str]) -> dict[str, Any]:
        """Store MFA setup data temporarily in Redis (expires in 5 minutes)."""
        mfa_data = {
            "user_id": user_id,
            "secret": secret,
            "backup_codes": backup_codes,
            "created_at": utcnow().isoformat(),
        }
        if self.redis:
            await self.redis.setex(
                f"mfa_setup:{user_id}", MFA_SETUP_TTL_SECONDS, json.dumps(mfa_data)
            )
        return mfa_data

    async def get_mfa_setup(self, user_id: int) -> dict[str, Any] | None:
        """Retrieve MFA setup data from Redis."""
        if not self.redis:
            return None
        raw = await self.redis.get(f"mfa_setup:{user_id}")
        if not raw:
            return None
        return json.loads(raw)

    async def enable_mfa(self, user_id: int, secret: str, backup_codes: list[str]) -> None:
        """Enable MFA for user."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(mfa_enabled=True, mfa_secret=secret, backup_codes=backup_codes)
        )
        await self.db.execute(query)
        await self.db.commit()

        # Clean up temporary setup data
        # await cache.delete(f"mfa_setup:{user_id}")

    async def disable_mfa(self, user_id: int) -> None:
        """Disable MFA for user."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(mfa_enabled=False, mfa_secret=None, backup_codes=None)
        )
        await self.db.execute(query)
        await self.db.commit()

    async def verify_backup_code(self, user_id: int, backup_code: str) -> bool:
        """Verify and consume a backup code."""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not user.backup_codes:
            return False

        if backup_code in user.backup_codes:
            # Remove used backup code
            user.backup_codes.remove(backup_code)
            await self.db.commit()
            return True

        return False

    async def register_device(
        self, user_id: int, device_name: str, device_type: str, device_fingerprint: str
    ) -> DeviceRegistration:
        """Register a new trusted device."""
        device_token = secrets.token_urlsafe(32)

        device = DeviceRegistration(
            user_id=user_id,
            device_name=device_name,
            device_type=device_type,
            device_fingerprint=device_fingerprint,
            device_token=device_token,
            is_trusted=False,
            last_used_at=utcnow(),
        )

        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)

        return device

    async def get_user_devices(self, user_id: int) -> list[DeviceRegistration]:
        """Get user's registered devices."""
        query = (
            select(DeviceRegistration)
            .where(and_(DeviceRegistration.user_id == user_id, DeviceRegistration.is_active))
            .order_by(DeviceRegistration.last_used_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def revoke_device(self, user_id: int, device_id: int) -> None:
        """Revoke a trusted device."""
        query = (
            update(DeviceRegistration)
            .where(and_(DeviceRegistration.id == device_id, DeviceRegistration.user_id == user_id))
            .values(is_active=False)
        )
        await self.db.execute(query)
        await self.db.commit()

    async def verify_social_token(
        self, provider: str, access_token: str, id_token: str | None = None
    ) -> dict[str, Any] | None:
        """Verify social authentication token."""
        # Implementation would depend on the social provider
        # This is a placeholder for the actual verification logic

        if provider == "google":
            return await self._verify_google_token(access_token, id_token)
        elif provider == "github":
            return await self._verify_github_token(access_token)
        elif provider == "linkedin":
            return await self._verify_linkedin_token(access_token)

        return None

    async def _verify_google_token(
        self, access_token: str, id_token: str | None = None
    ) -> dict[str, Any] | None:
        """Verify Google OAuth token."""
        # Placeholder implementation
        # In real implementation, verify with Google's API
        return {
            "id": "google_user_id",
            "email": "user@example.com",
            "name": "John Doe",
            "picture": "https://example.com/avatar.jpg",
        }

    async def _verify_github_token(self, access_token: str) -> dict[str, Any] | None:
        """Verify GitHub OAuth token."""
        # Placeholder implementation
        return {
            "id": "github_user_id",
            "email": "user@example.com",
            "name": "John Doe",
            "avatar_url": "https://example.com/avatar.jpg",
        }

    async def _verify_linkedin_token(self, access_token: str) -> dict[str, Any] | None:
        """Verify LinkedIn OAuth token."""
        # Placeholder implementation
        return {"id": "linkedin_user_id", "email": "user@example.com", "name": "John Doe"}

    async def get_or_create_social_user(
        self,
        provider: str,
        social_id: str,
        email: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """Get existing user or create new one from social auth."""
        # Try to find existing user by email
        user = await self.get_user_by_email(email)

        if user:
            # Update social ID if not set
            social_field = f"{provider}_id"
            if hasattr(user, social_field) and not getattr(user, social_field):
                setattr(user, social_field, social_id)
                await self.db.commit()
            return user

        # Create new user
        user = User(
            email=email,
            hashed_password=security_manager.get_password_hash(
                secrets.token_urlsafe(32)
            ),  # Random password
            full_name=full_name,
            avatar_url=avatar_url,
            is_active=True,
            is_verified=True,  # Social accounts are pre-verified
        )

        # Set social ID
        social_field = f"{provider}_id"
        if hasattr(user, social_field):
            setattr(user, social_field, social_id)

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def send_magic_link_email(self, email: str, token: str) -> None:
        """Send magic link via email."""
        magic_link = f"https://example.com/auth/magic-link?token={token}"

        await self.email_service.send_magic_link_email(email, magic_link)

    async def send_magic_link_sms(self, phone: str, token: str) -> None:
        """Send magic link via SMS."""
        # Placeholder for SMS implementation

    async def create_user_session(
        self,
        user_id: int,
        session_id: str,
        device_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """Create a new user session."""
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            last_activity_at=utcnow(),
            expires_at=utcnow() + timedelta(days=30),
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_user_sessions(self, user_id: int, redis_client) -> list[dict[str, Any]]:
        """Get user's active sessions."""
        # This would typically involve both database and Redis
        query = (
            select(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active,
                    UserSession.expires_at > utcnow(),
                )
            )
            .order_by(UserSession.last_activity_at.desc())
        )
        result = await self.db.execute(query)
        sessions = result.scalars().all()

        return [
            {
                "session_id": session.session_id,
                "device_info": {"device_id": session.device_id},
                "ip_address": session.ip_address,
                "last_activity": session.last_activity_at,
                "is_current": False,  # Would need to check current session
            }
            for session in sessions
        ]

    async def revoke_session(self, user_id: int, session_id: str, redis_client) -> None:
        """Revoke a specific session."""
        query = (
            update(UserSession)
            .where(and_(UserSession.user_id == user_id, UserSession.session_id == session_id))
            .values(is_active=False)
        )
        await self.db.execute(query)
        await self.db.commit()

        # Also remove from Redis if cached
        # await redis_client.delete(f"session:{session_id}")

    async def revoke_all_sessions(self, user_id: int, redis_client) -> int:
        """Revoke all user sessions except current."""
        query = update(UserSession).where(UserSession.user_id == user_id).values(is_active=False)
        result = await self.db.execute(query)
        await self.db.commit()

        return int(getattr(result, "rowcount", 0) or 0)
