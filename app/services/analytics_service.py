# File: app/services/analytics_service.py

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.course import Course, CourseReview, Enrollment, EnrollmentStatus

_TIME_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}


class AnalyticsService:
    """Service for generating course and instructor analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Course analytics
    # ------------------------------------------------------------------

    async def get_course_analytics(self, course_id: int, time_range: str = "30d") -> dict[str, Any]:
        """Return analytics data matching the CourseAnalytics schema."""
        days = _TIME_RANGE_DAYS.get(time_range, 30)
        since = utcnow() - timedelta(days=days)

        # Total enrollments
        total_enroll_q = select(func.count(Enrollment.id)).where(Enrollment.course_id == course_id)
        total_enroll = (await self.db.execute(total_enroll_q)).scalar() or 0

        # Enrollments within time range
        recent_enroll_q = select(func.count(Enrollment.id)).where(
            and_(Enrollment.course_id == course_id, Enrollment.enrolled_at >= since)
        )
        recent_enroll = (await self.db.execute(recent_enroll_q)).scalar() or 0

        # Completion count
        completed_q = select(func.count(Enrollment.id)).where(
            and_(
                Enrollment.course_id == course_id,
                Enrollment.status == EnrollmentStatus.COMPLETED,
            )
        )
        completed = (await self.db.execute(completed_q)).scalar() or 0

        # Average rating
        avg_rating_q = select(func.avg(CourseReview.rating)).where(
            CourseReview.course_id == course_id
        )
        avg_rating = (await self.db.execute(avg_rating_q)).scalar() or 0.0

        # Total reviews
        total_reviews_q = select(func.count(CourseReview.id)).where(
            CourseReview.course_id == course_id
        )
        total_reviews = (await self.db.execute(total_reviews_q)).scalar() or 0

        completion_rate = (completed / total_enroll * 100) if total_enroll else 0.0
        conversion_rate = (recent_enroll / max(total_enroll, 1)) * 100

        return {
            "course_id": course_id,
            "total_views": total_enroll,  # proxy until view tracking added
            "total_enrollments": total_enroll,
            "conversion_rate": round(conversion_rate, 2),
            "completion_rate": round(completion_rate, 2),
            "average_rating": round(float(avg_rating), 2),
            "total_reviews": total_reviews,
            "revenue_total": Decimal("0.00"),
            "revenue_monthly": Decimal("0.00"),
            "refund_rate": 0.0,
            "student_satisfaction": round(float(avg_rating) * 20, 2),  # 0-100 scale
            "engagement_metrics": {},
            "traffic_sources": {},
            "demographics": {},
            "performance_trends": {},
            "top_dropout_points": [],
        }

    # ------------------------------------------------------------------
    # Instructor dashboard
    # ------------------------------------------------------------------

    async def get_instructor_dashboard(
        self, instructor_id: int, time_range: str = "30d"
    ) -> dict[str, Any]:
        """Return aggregated dashboard metrics for an instructor."""
        days = _TIME_RANGE_DAYS.get(time_range, 30)
        utcnow() - timedelta(days=days)

        # Courses owned
        courses_q = select(Course).where(Course.instructor_id == instructor_id)
        courses_result = await self.db.execute(courses_q)
        courses: list[Course] = list(courses_result.scalars().all())
        course_ids = [c.id for c in courses]

        total_students = 0
        avg_rating = 0.0

        if course_ids:
            student_q = select(func.count(Enrollment.id)).where(
                Enrollment.course_id.in_(course_ids)
            )
            total_students = (await self.db.execute(student_q)).scalar() or 0

            rating_q = select(func.avg(CourseReview.rating)).where(
                CourseReview.course_id.in_(course_ids)
            )
            avg_rating = float((await self.db.execute(rating_q)).scalar() or 0.0)

        return {
            "total_courses": len(courses),
            "total_students": total_students,
            "total_revenue": 0.0,
            "avg_rating": round(avg_rating, 2),
            "recent_activity": [],
            "top_courses": [{"id": c.id, "title": c.title, "students": 0} for c in courses[:5]],
            "engagement_metrics": {},
            "growth_metrics": {},
        }
