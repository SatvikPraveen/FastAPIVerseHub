# File: app/services/advanced_course_service.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.user import User


@dataclass
class LearningPath:
    """Lightweight in-memory representation of a learning path."""

    id: int
    title: str
    description: str
    courses: list[dict[str, Any]]
    estimated_duration_weeks: int
    difficulty: str
    completion_rate: float = 0.0
    user_progress: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


class AdvancedCourseService:
    """Service for advanced course operations: AI recommendations, learning paths, analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # User learning profile
    # ------------------------------------------------------------------

    async def get_user_learning_profile(self, user_id: int) -> dict[str, Any]:
        """Aggregate learning history and preferences for a user."""
        user_q = select(User).where(User.id == user_id)
        result = await self.db.execute(user_q)
        user = result.scalar_one_or_none()
        if not user:
            return {}

        # Count completed enrollments
        completed_q = select(Enrollment).where(
            and_(
                Enrollment.user_id == user_id,
                Enrollment.status == EnrollmentStatus.COMPLETED,
            )
        )
        completed_result = await self.db.execute(completed_q)
        completed_enrollments = list(completed_result.scalars().all())

        return {
            "user_id": user_id,
            "interests": user.interests or [],
            "learning_style": user.learning_style,
            "skill_level": user.skill_level,
            "average_skill_level": user.skill_level,
            "completed_courses": len(completed_enrollments),
            "timezone": user.timezone,
            "language": user.language,
        }

    # ------------------------------------------------------------------
    # Learning paths
    # ------------------------------------------------------------------

    async def get_learning_paths(
        self,
        category: str | None = None,
        difficulty: str | None = None,
        user_id: int | None = None,
    ) -> list[LearningPath]:
        """Return available learning paths (stub — extend with a DB model when ready)."""
        # Placeholder: return sensible defaults until a LearningPath DB model exists.
        paths = [
            LearningPath(
                id=1,
                title="Backend Developer Path",
                description="Become a proficient backend developer with Python and FastAPI.",
                courses=[],
                estimated_duration_weeks=12,
                difficulty="intermediate",
                completion_rate=0.0,
                user_progress={},
            ),
            LearningPath(
                id=2,
                title="Full-Stack Fundamentals",
                description="Learn both frontend and backend development from scratch.",
                courses=[],
                estimated_duration_weeks=24,
                difficulty="beginner",
                completion_rate=0.0,
                user_progress={},
            ),
        ]

        if difficulty:
            paths = [p for p in paths if p.difficulty == difficulty]

        return paths

    async def save_learning_path(
        self, user_id: int, learning_path_data: dict[str, Any]
    ) -> LearningPath:
        """Persist a generated learning path (stub returns an in-memory object)."""
        return LearningPath(
            id=learning_path_data.get("id", 1),
            title=learning_path_data.get("title", "Custom Learning Path"),
            description=learning_path_data.get("description", ""),
            courses=learning_path_data.get("courses", []),
            estimated_duration_weeks=learning_path_data.get("estimated_duration_weeks", 4),
            difficulty=learning_path_data.get("difficulty_preference", "intermediate"),
        )

    async def send_learning_path_notification(self, user_id: int, path_id: int) -> None:
        """Background task: notify user about their new learning path."""
        # Notification sending would be wired to EmailService / push notifications.

    # ------------------------------------------------------------------
    # Course helpers
    # ------------------------------------------------------------------

    async def get_course_by_id(self, course_id: int) -> Course | None:
        """Retrieve a course by its primary key."""
        query = select(Course).where(Course.id == course_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_course_performance_data(
        self, course_id: int, time_range: str = "30d"
    ) -> dict[str, Any]:
        """Get aggregated performance data for a course."""
        course = await self.get_course_by_id(course_id)
        if not course:
            return {}

        enrollments_q = select(Enrollment).where(Enrollment.course_id == course_id)
        enrollments_result = await self.db.execute(enrollments_q)
        enrollments = list(enrollments_result.scalars().all())

        total = len(enrollments)
        completed = sum(1 for e in enrollments if e.status == EnrollmentStatus.COMPLETED)

        return {
            "course_id": course_id,
            "total_enrollments": total,
            "completed": completed,
            "completion_rate": (completed / total * 100) if total else 0.0,
            "time_range": time_range,
        }

    async def save_optimization_report(
        self, course_id: int, report: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist an AI-generated optimization report (stub)."""
        return {"course_id": course_id, "report": report, "saved_at": utcnow().isoformat()}

    async def apply_optimization_suggestions(
        self, course_id: int, suggestions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Apply automated optimization suggestions to a course (stub)."""
        return {"course_id": course_id, "applied": len(suggestions), "status": "queued"}
