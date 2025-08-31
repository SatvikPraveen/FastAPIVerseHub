# File: app/services/user_service.py

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import and_, func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import security_manager
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for user management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        query = select(User).where(and_(User.id == user_id, User.deleted_at.is_(None)))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        query = select(User).where(and_(User.email == email, User.deleted_at.is_(None)))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_user(self, user_create: UserCreate) -> User:
        """Create a new user."""
        hashed_password = security_manager.get_password_hash(user_create.password)
        
        user = User(
            email=user_create.email,
            hashed_password=hashed_password,
            full_name=user_create.full_name,
            is_active=user_create.is_active,
            is_superuser=user_create.is_superuser
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> User:
        """Update user information."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        update_data = user_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def delete_user(self, user_id: int) -> bool:
        """Soft delete a user."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(
                deleted_at=datetime.utcnow(),
                is_active=False
            )
        )
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
        is_active_filter: Optional[bool] = None,
        sort_by: Optional[str] = None,
        order: str = "asc"
    ) -> Tuple[List[User], int]:
        """Get users with filtering and pagination."""
        query = select(User).where(User.deleted_at.is_(None))
        count_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
        
        # Apply filters
        if search_query:
            search_filter = or_(
                User.email.ilike(f"%{search_query}%"),
                User.full_name.ilike(f"%{search_query}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        if is_active_filter is not None:
            query = query.where(User.is_active == is_active_filter)
            count_query = count_query.where(User.is_active == is_active_filter)
        
        # Apply sorting
        if sort_by:
            sort_field = getattr(User, sort_by, User.created_at)
            if order.lower() == "desc":
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(User.created_at.desc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute queries
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        return users, total
    
    async def activate_user(self, user_id: int) -> bool:
        """Activate a user account."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=True, updated_at=datetime.utcnow())
        )
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}
        
        # Calculate account age
        account_age_days = (datetime.utcnow() - user.created_at).days
        
        # Get course statistics (placeholder queries)
        # In real implementation, these would join with course/enrollment tables
        stats = {
            "total_courses": 0,
            "completed_courses": 0,
            "in_progress_courses": 0,
            "total_uploads": 0,
            "account_age_days": account_age_days,
            "last_activity": user.last_activity_at,
            "login_count": user.login_count,
            "learning_streak_days": 0,
            "certificates_earned": 0,
            "total_study_time_hours": 0,
            "favorite_categories": [],
            "skill_progress": {},
            "achievements": [],
            "social_connections": 0
        }
        
        # TODO: Implement actual queries for course data
        # This would involve joining with enrollment, course, and other related tables
        
        return stats
    
    async def search_users(
        self,
        query: str,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """Search users by various criteria."""
        search_query = select(User).where(
            and_(
                User.deleted_at.is_(None),
                or_(
                    User.email.ilike(f"%{query}%"),
                    User.full_name.ilike(f"%{query}%"),
                    User.bio.ilike(f"%{query}%")
                )
            )
        )
        
        if filters:
            if filters.get("is_active") is not None:
                search_query = search_query.where(User.is_active == filters["is_active"])
            
            if filters.get("skill_level"):
                search_query = search_query.where(User.skill_level == filters["skill_level"])
            
            if filters.get("location"):
                search_query = search_query.where(User.location.ilike(f"%{filters['location']}%"))
        
        search_query = search_query.limit(limit)
        result = await self.db.execute(search_query)
        
        return result.scalars().all()
    
    async def update_user_activity(self, user_id: int) -> None:
        """Update user's last activity timestamp."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(last_activity_at=datetime.utcnow())
        )
        await self.db.execute(query)
        await self.db.commit()
    
    async def update_user_preferences(
        self, 
        user_id: int, 
        preferences: Dict[str, Any]
    ) -> User:
        """Update user preferences."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Update preference fields
        for key, value in preferences.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def get_user_learning_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user's learning profile and preferences."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}
        
        return {
            "learning_style": user.learning_style,
            "skill_level": user.skill_level,
            "interests": user.interests or [],
            "timezone": user.timezone,
            "language": user.language,
            "email_notifications": user.email_notifications,
            "push_notifications": user.push_notifications,
            "created_at": user.created_at,
            "last_activity": user.last_activity_at
        }
    
    async def get_users_by_skill_level(self, skill_level: str) -> List[User]:
        """Get users by skill level."""
        query = select(User).where(
            and_(
                User.skill_level == skill_level,
                User.is_active == True,
                User.deleted_at.is_(None)
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_recently_active_users(self, days: int = 7) -> List[User]:
        """Get users who were active in the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(User).where(
            and_(
                User.last_activity_at >= cutoff_date,
                User.is_active == True,
                User.deleted_at.is_(None)
            )
        ).order_by(User.last_activity_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count_users_by_status(self) -> Dict[str, int]:
        """Count users by different status categories."""
        total_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
        active_query = select(func.count(User.id)).where(
            and_(User.is_active == True, User.deleted_at.is_(None))
        )
        inactive_query = select(func.count(User.id)).where(
            and_(User.is_active == False, User.deleted_at.is_(None))
        )
        verified_query = select(func.count(User.id)).where(
            and_(User.is_verified == True, User.deleted_at.is_(None))
        )
        
        total_result = await self.db.execute(total_query)
        active_result = await self.db.execute(active_query)
        inactive_result = await self.db.execute(inactive_query)
        verified_result = await self.db.execute(verified_query)
        
        return {
            "total": total_result.scalar(),
            "active": active_result.scalar(),
            "inactive": inactive_result.scalar(),
            "verified": verified_result.scalar()
        }