# File: app/services/user_service.py

from datetime import timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import security_manager
from app.core.time import utcnow
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        query = select(User).where(and_(User.id == user_id, User.deleted_at.is_(None)))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
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
            is_superuser=user_create.is_superuser,
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

        update_data = user_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def delete_user(self, user_id: int) -> bool:
        """Soft delete a user."""
        query = update(User).where(User.id == user_id).values(deleted_at=utcnow(), is_active=False)
        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        search_query: str | None = None,
        is_active_filter: bool | None = None,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> tuple[list[User], int]:
        """Get users with filtering and pagination."""
        query = select(User).where(User.deleted_at.is_(None))
        count_query = select(func.count(User.id)).where(User.deleted_at.is_(None))

        # Apply filters
        if search_query:
            search_filter = or_(
                User.email.ilike(f"%{search_query}%"), User.full_name.ilike(f"%{search_query}%")
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
        query = update(User).where(User.id == user_id).values(is_active=True, updated_at=utcnow())
        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account."""
        query = update(User).where(User.id == user_id).values(is_active=False, updated_at=utcnow())
        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    async def get_user_stats(self, user_id: int) -> dict[str, Any]:
        """Get comprehensive user statistics via real DB queries."""
        from app.models.course import Enrollment, EnrollmentStatus
        from app.models.user import FileUpload

        user = await self.get_user_by_id(user_id)
        if not user:
            return {}

        account_age_days = (utcnow() - user.created_at).days

        # Total enrollments
        total_q = select(func.count(Enrollment.id)).where(Enrollment.user_id == user_id)
        total_result = await self.db.execute(total_q)
        total_courses = total_result.scalar() or 0

        # Completed enrollments
        completed_q = select(func.count(Enrollment.id)).where(
            and_(Enrollment.user_id == user_id, Enrollment.status == EnrollmentStatus.COMPLETED)
        )
        completed_result = await self.db.execute(completed_q)
        completed_courses = completed_result.scalar() or 0

        # Non-deleted uploads
        uploads_q = select(func.count(FileUpload.id)).where(
            and_(FileUpload.user_id == user_id, FileUpload.is_deleted.is_(False))
        )
        uploads_result = await self.db.execute(uploads_q)
        total_uploads = uploads_result.scalar() or 0

        return {
            "total_courses": total_courses,
            "completed_courses": completed_courses,
            "in_progress_courses": total_courses - completed_courses,
            "total_uploads": total_uploads,
            "account_age_days": account_age_days,
            "last_activity": user.last_activity_at,
            "login_count": user.login_count,
            "learning_streak_days": 0,
            "certificates_earned": completed_courses,
            "total_study_time_hours": 0,
            "favorite_categories": [],
            "skill_progress": {},
            "achievements": [],
            "social_connections": 0,
        }

    async def search_users(
        self, query: str, limit: int = 20, filters: dict[str, Any] | None = None
    ) -> list[User]:
        """Search users by various criteria."""
        search_query = select(User).where(
            and_(
                User.deleted_at.is_(None),
                or_(
                    User.email.ilike(f"%{query}%"),
                    User.full_name.ilike(f"%{query}%"),
                    User.bio.ilike(f"%{query}%"),
                ),
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
        query = update(User).where(User.id == user_id).values(last_activity_at=utcnow())
        await self.db.execute(query)
        await self.db.commit()

    async def update_user_preferences(self, user_id: int, preferences: dict[str, Any]) -> User:
        """Update user preferences."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Update preference fields
        for key, value in preferences.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_user_learning_profile(self, user_id: int) -> dict[str, Any]:
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
            "last_activity": user.last_activity_at,
        }

    async def get_users_by_skill_level(self, skill_level: str) -> list[User]:
        """Get users by skill level."""
        query = select(User).where(
            and_(User.skill_level == skill_level, User.is_active, User.deleted_at.is_(None))
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_recently_active_users(self, days: int = 7) -> list[User]:
        """Get users who were active in the last N days."""
        cutoff_date = utcnow() - timedelta(days=days)

        query = (
            select(User)
            .where(
                and_(
                    User.last_activity_at >= cutoff_date, User.is_active, User.deleted_at.is_(None)
                )
            )
            .order_by(User.last_activity_at.desc())
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_users_by_status(self) -> dict[str, int]:
        """Count users by different status categories."""
        total_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
        active_query = select(func.count(User.id)).where(
            and_(User.is_active, User.deleted_at.is_(None))
        )
        inactive_query = select(func.count(User.id)).where(
            and_(not User.is_active, User.deleted_at.is_(None))
        )
        verified_query = select(func.count(User.id)).where(
            and_(User.is_verified, User.deleted_at.is_(None))
        )

        total_result = await self.db.execute(total_query)
        active_result = await self.db.execute(active_query)
        inactive_result = await self.db.execute(inactive_query)
        verified_result = await self.db.execute(verified_query)

        return {
            "total": total_result.scalar(),
            "active": active_result.scalar(),
            "inactive": inactive_result.scalar(),
            "verified": verified_result.scalar(),
        }
