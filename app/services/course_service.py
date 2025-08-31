# File: app/services/course_service.py

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, Enrollment, CourseReview, Lesson
from app.models.user import User
from app.schemas.course import CourseCreate, CourseUpdate


class CourseService:
    """Service for course management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_course_by_id(self, course_id: int) -> Optional[Course]:
        """Get course by ID."""
        query = select(Course).where(Course.id == course_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_course_by_slug(self, slug: str) -> Optional[Course]:
        """Get course by slug."""
        query = select(Course).where(Course.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_course(self, course_create: CourseCreate, instructor_id: int) -> Course:
        """Create a new course."""
        # Generate slug from title
        slug = self._generate_slug(course_create.title)
        
        course = Course(
            title=course_create.title,
            slug=slug,
            description=course_create.description,
            short_description=course_create.short_description,
            instructor_id=instructor_id,
            category=course_create.category,
            subcategory=course_create.subcategory,
            difficulty=course_create.difficulty,
            estimated_duration_hours=course_create.estimated_duration_hours,
            language=course_create.language,
            tags=course_create.tags,
            learning_objectives=course_create.learning_objectives,
            prerequisites=course_create.prerequisites,
            price=course_create.price,
            original_price=course_create.original_price,
            is_free=course_create.is_free
        )
        
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        
        return course
    
    async def update_course(self, course_id: int, course_update: CourseUpdate) -> Course:
        """Update course information."""
        course = await self.get_course_by_id(course_id)
        if not course:
            raise ValueError("Course not found")
        
        update_data = course_update.dict(exclude_unset=True)
        
        # Update slug if title changed
        if "title" in update_data:
            update_data["slug"] = self._generate_slug(update_data["title"])
        
        for field, value in update_data.items():
            setattr(course, field, value)
        
        course.updated_at = datetime.utcnow()
        course.last_updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(course)
        
        return course
    
    async def delete_course(self, course_id: int) -> bool:
        """Delete a course."""
        query = delete(Course).where(Course.id == course_id)
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def get_courses(
        self,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
        category_filter: Optional[str] = None,
        difficulty_filter: Optional[str] = None,
        is_published_filter: Optional[bool] = None,
        user_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        order: str = "asc"
    ) -> Tuple[List[Course], int]:
        """Get courses with filtering and pagination."""
        query = select(Course)
        count_query = select(func.count(Course.id))
        
        # Apply filters
        filters = []
        
        if search_query:
            search_filter = or_(
                Course.title.ilike(f"%{search_query}%"),
                Course.description.ilike(f"%{search_query}%"),
                Course.short_description.ilike(f"%{search_query}%")
            )
            filters.append(search_filter)
        
        if category_filter:
            filters.append(Course.category == category_filter)
        
        if difficulty_filter:
            filters.append(Course.difficulty == difficulty_filter)
        
        if is_published_filter is not None:
            filters.append(Course.is_published == is_published_filter)
        
        if user_id:
            filters.append(Course.instructor_id == user_id)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Apply sorting
        if sort_by:
            sort_field = getattr(Course, sort_by, Course.created_at)
            if order.lower() == "desc":
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(Course.created_at.desc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute queries
        result = await self.db.execute(query)
        courses = result.scalars().all()
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        return courses, total
    
    async def publish_course(self, course_id: int) -> Course:
        """Publish a course."""
        course = await self.get_course_by_id(course_id)
        if not course:
            raise ValueError("Course not found")
        
        course.is_published = True
        course.status = "published"
        course.published_at = datetime.utcnow()
        course.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(course)
        
        return course
    
    async def unpublish_course(self, course_id: int) -> Course:
        """Unpublish a course."""
        course = await self.get_course_by_id(course_id)
        if not course:
            raise ValueError("Course not found")
        
        course.is_published = False
        course.status = "draft"
        course.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(course)
        
        return course
    
    async def enroll_user(self, course_id: int, user_id: int) -> Enrollment:
        """Enroll a user in a course."""
        enrollment = Enrollment(
            user_id=user_id,
            course_id=course_id,
            status="active",
            enrolled_at=datetime.utcnow()
        )
        
        self.db.add(enrollment)
        
        # Update course enrollment count
        query = (
            update(Course)
            .where(Course.id == course_id)
            .values(
                total_enrollments=Course.total_enrollments + 1,
                active_enrollments=Course.active_enrollments + 1
            )
        )
        await self.db.execute(query)
        
        await self.db.commit()
        await self.db.refresh(enrollment)
        
        return enrollment
    
    async def unenroll_user(self, course_id: int, user_id: int) -> None:
        """Unenroll a user from a course."""
        query = (
            update(Enrollment)
            .where(and_(
                Enrollment.course_id == course_id,
                Enrollment.user_id == user_id
            ))
            .values(status="dropped")
        )
        await self.db.execute(query)
        
        # Update course enrollment count
        course_query = (
            update(Course)
            .where(Course.id == course_id)
            .values(active_enrollments=Course.active_enrollments - 1)
        )
        await self.db.execute(course_query)
        
        await self.db.commit()
    
    async def is_user_enrolled(self, course_id: int, user_id: int) -> bool:
        """Check if user is enrolled in a course."""
        query = select(Enrollment).where(and_(
            Enrollment.course_id == course_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active"
        ))
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def get_course_enrollments(
        self,
        course_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get course enrollments with user information."""
        query = (
            select(Enrollment, User)
            .join(User, Enrollment.user_id == User.id)
            .where(Enrollment.course_id == course_id)
            .order_by(Enrollment.enrolled_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        count_query = (
            select(func.count(Enrollment.id))
            .where(Enrollment.course_id == course_id)
        )
        
        result = await self.db.execute(query)
        enrollments_with_users = result.all()
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        enrollments = []
        for enrollment, user in enrollments_with_users:
            enrollments.append({
                "enrollment_id": enrollment.id,
                "user_id": user.id,
                "user_name": user.full_name or user.email,
                "user_email": user.email,
                "status": enrollment.status,
                "progress_percentage": float(enrollment.progress_percentage),
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at
            })
        
        return enrollments, total
    
    async def get_course_stats(self, course_id: int) -> Dict[str, Any]:
        """Get comprehensive course statistics."""
        # Get basic enrollment stats
        enrollment_query = (
            select(
                func.count(Enrollment.id).label("total_enrollments"),
                func.count(Enrollment.id).filter(Enrollment.status == "completed").label("completed_enrollments"),
                func.avg(Enrollment.progress_percentage).label("avg_progress")
            )
            .where(Enrollment.course_id == course_id)
        )
        
        # Get review stats
        review_query = (
            select(
                func.count(CourseReview.id).label("total_reviews"),
                func.avg(CourseReview.rating).label("avg_rating")
            )
            .where(CourseReview.course_id == course_id)
        )
        
        enrollment_result = await self.db.execute(enrollment_query)
        enrollment_stats = enrollment_result.first()
        
        review_result = await self.db.execute(review_query)
        review_stats = review_result.first()
        
        return {
            "total_enrollments": enrollment_stats.total_enrollments or 0,
            "completed_enrollments": enrollment_stats.completed_enrollments or 0,
            "average_progress": float(enrollment_stats.avg_progress or 0),
            "total_reviews": review_stats.total_reviews or 0,
            "average_rating": float(review_stats.avg_rating or 0)
        }
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all course categories with counts."""
        query = (
            select(
                Course.category,
                func.count(Course.id).label("count")
            )
            .where(Course.is_published == True)
            .group_by(Course.category)
            .order_by(func.count(Course.id).desc())
        )
        
        result = await self.db.execute(query)
        categories = result.all()
        
        return [
            {
                "name": category.category,
                "count": category.count,
                "description": f"Learn {category.category.lower()}"
            }
            for category in categories
        ]
    
    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        import re
        
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Add timestamp to ensure uniqueness
        timestamp = str(int(datetime.utcnow().timestamp()))[-4:]
        return f"{slug}-{timestamp}"