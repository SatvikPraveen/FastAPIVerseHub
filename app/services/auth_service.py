# Auth services - TODO: Implement business logic
# File: app/services/auth_service.py

import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import security_manager
from app.models.user import User, DeviceRegistration, UserSession
from app.schemas.auth import UserRegistration
from app.common.email_utils import EmailService


class AuthService:
    """Authentication service for user management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
    
    async def create_user(self, user_data: UserRegistration) -> User:
        """Create a new user account."""
        hashed_password = security_manager.get_password_hash(user_data.password)
        
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,
            is_verified=False
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        # Send welcome email
        await self.email_service.send_welcome_email(user.email, user.full_name)
        
        return user
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not security_manager.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
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
                last_login_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                login_count=User.login_count + 1
            )
        )
        await self.db.execute(query)
        await self.db.commit()
    
    async def change_password(self, user_id: int, new_password: str) -> None:
        """Change user's password."""
        hashed_password = security_manager.get_password_hash(new_password)
        
        query = (
            update(User)
            .where(User.id == user_id)
            .values(hashed_password=hashed_password)
        )
        await self.db.execute(query)
        await self.db.commit()
    
    async def setup_mfa(self, user_id: int, secret: str, backup_codes: List[str]) -> Dict[str, Any]:
        """Setup MFA for user (temporary storage)."""
        # In a real implementation, you might store this in Redis or a temporary table
        mfa_setup = {
            "user_id": user_id,
            "secret": secret,
            "backup_codes": backup_codes,
            "created_at": datetime.utcnow()
        }
        
        # Store in cache/temporary storage
        # await cache.set(f"mfa_setup:{user_id}", mfa_setup, expire=300)
        
        return mfa_setup
    
    async def get_mfa_setup(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get MFA setup data."""
        # Retrieve from cache/temporary storage
        # return await cache.get(f"mfa_setup:{user_id}")
        
        # For now, return dummy data
        return {
            "user_id": user_id,
            "secret": "DUMMY_SECRET",
            "backup_codes": ["12345678", "87654321"],
            "created_at": datetime.utcnow()
        }
    
    async def enable_mfa(self, user_id: int, secret: str, backup_codes: List[str]) -> None:
        """Enable MFA for user."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(
                mfa_enabled=True,
                mfa_secret=secret,
                backup_codes=backup_codes
            )
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
            .values(
                mfa_enabled=False,
                mfa_secret=None,
                backup_codes=None
            )
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
        self, 
        user_id: int, 
        device_name: str, 
        device_type: str, 
        device_fingerprint: str
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
            last_used_at=datetime.utcnow()
        )
        
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        
        return device
    
    async def get_user_devices(self, user_id: int) -> List[DeviceRegistration]:
        """Get user's registered devices."""
        query = (
            select(DeviceRegistration)
            .where(and_(
                DeviceRegistration.user_id == user_id,
                DeviceRegistration.is_active == True
            ))
            .order_by(DeviceRegistration.last_used_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def revoke_device(self, user_id: int, device_id: int) -> None:
        """Revoke a trusted device."""
        query = (
            update(DeviceRegistration)
            .where(and_(
                DeviceRegistration.id == device_id,
                DeviceRegistration.user_id == user_id
            ))
            .values(is_active=False)
        )
        await self.db.execute(query)
        await self.db.commit()
    
    async def verify_social_token(
        self, 
        provider: str, 
        access_token: str, 
        id_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
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
    
    async def _verify_google_token(self, access_token: str, id_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Verify Google OAuth token."""
        # Placeholder implementation
        # In real implementation, verify with Google's API
        return {
            "id": "google_user_id",
            "email": "user@example.com",
            "name": "John Doe",
            "picture": "https://example.com/avatar.jpg"
        }
    
    async def _verify_github_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Verify GitHub OAuth token."""
        # Placeholder implementation
        return {
            "id": "github_user_id",
            "email": "user@example.com",
            "name": "John Doe",
            "avatar_url": "https://example.com/avatar.jpg"
        }
    
    async def _verify_linkedin_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Verify LinkedIn OAuth token."""
        # Placeholder implementation
        return {
            "id": "linkedin_user_id",
            "email": "user@example.com",
            "name": "John Doe"
        }
    
    async def get_or_create_social_user(
        self,
        provider: str,
        social_id: str,
        email: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None
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
            hashed_password=security_manager.get_password_hash(secrets.token_urlsafe(32)),  # Random password
            full_name=full_name,
            avatar_url=avatar_url,
            is_active=True,
            is_verified=True  # Social accounts are pre-verified
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
        pass
    
    async def create_user_session(
        self,
        user_id: int,
        session_id: str,
        device_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """Create a new user session."""
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            last_activity_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        return session
    
    async def get_user_sessions(self, user_id: int, redis_client) -> List[Dict[str, Any]]:
        """Get user's active sessions."""
        # This would typically involve both database and Redis
        query = (
            select(UserSession)
            .where(and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ))
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
                "is_current": False  # Would need to check current session
            }
            for session in sessions
        ]
    
    async def revoke_session(self, user_id: int, session_id: str, redis_client) -> None:
        """Revoke a specific session."""
        query = (
            update(UserSession)
            .where(and_(
                UserSession.user_id == user_id,
                UserSession.session_id == session_id
            ))
            .values(is_active=False)
        )
        await self.db.execute(query)
        await self.db.commit()
        
        # Also remove from Redis if cached
        # await redis_client.delete(f"session:{session_id}")
    
    async def revoke_all_sessions(self, user_id: int, redis_client) -> int:
        """Revoke all user sessions except current."""
        query = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(is_active=False)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount