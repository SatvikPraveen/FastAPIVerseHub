# File: app/services/analytics_service.py

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

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
        since = utcnow() - timedelta(days=days)

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

        recent_enrollments = 0
        per_course: dict[int, int] = {}
        revenue = Decimal("0.00")
        if course_ids:
            per_course_rows = await self.db.execute(
                select(Enrollment.course_id, func.count(Enrollment.id))
                .where(Enrollment.course_id.in_(course_ids))
                .group_by(Enrollment.course_id)
            )
            per_course = {int(cid): int(n) for cid, n in per_course_rows.all()}
            recent_enrollments = (
                await self.db.execute(
                    select(func.count(Enrollment.id)).where(
                        and_(Enrollment.course_id.in_(course_ids), Enrollment.enrolled_at >= since)
                    )
                )
            ).scalar() or 0
            revenue = (
                await self.db.execute(
                    select(func.coalesce(func.sum(Enrollment.payment_amount), 0)).where(
                        Enrollment.course_id.in_(course_ids)
                    )
                )
            ).scalar() or Decimal("0.00")

        top_courses = sorted(courses, key=lambda c: per_course.get(c.id, 0), reverse=True)[:5]
        return {
            "total_courses": len(courses),
            "total_students": total_students,
            "total_revenue": float(revenue),
            "avg_rating": round(avg_rating, 2),
            "recent_activity": [
                {"type": "enrollments", "window_days": days, "count": int(recent_enrollments)}
            ],
            "top_courses": [
                {"id": c.id, "title": c.title, "students": per_course.get(c.id, 0)}
                for c in top_courses
            ],
            "engagement_metrics": {
                "students_per_course": round(total_students / len(courses), 2) if courses else 0.0,
            },
            "growth_metrics": {
                "new_enrollments": int(recent_enrollments),
                "window_days": days,
            },
        }

    # ------------------------------------------------------------------
    # Market trends
    # ------------------------------------------------------------------

    async def get_market_trends(
        self, category: str | None = None, time_range: str = "90d"
    ) -> dict[str, Any]:
        """Catalogue-wide demand and pricing signals derived from enrollments."""
        days = _TIME_RANGE_DAYS.get(time_range, 90)
        since = utcnow() - timedelta(days=days)

        course_filter: list[ColumnElement[bool]] = [Course.is_published.is_(True)]
        if category:
            course_filter.append(Course.category == category)

        # Enrollments per category inside the window
        demand_rows = await self.db.execute(
            select(Course.category, func.count(Enrollment.id).label("n"))
            .join(Enrollment, Enrollment.course_id == Course.id)
            .where(and_(*course_filter, Enrollment.enrolled_at >= since))
            .group_by(Course.category)
            .order_by(func.count(Enrollment.id).desc())
        )
        demand = [(str(cat), int(n)) for cat, n in demand_rows.all()]

        # Supply and pricing per category
        supply_rows = await self.db.execute(
            select(
                Course.category,
                func.count(Course.id),
                func.avg(Course.price),
                func.min(Course.price),
                func.max(Course.price),
            )
            .where(and_(*course_filter))
            .group_by(Course.category)
        )
        supply = {
            str(cat): {
                "courses": int(n),
                "avg_price": round(float(avg or 0), 2),
                "min_price": float(lo or 0),
                "max_price": float(hi or 0),
            }
            for cat, n, avg, lo, hi in supply_rows.all()
        }

        # Tag frequency across published courses as a proxy for skill demand
        tag_rows = await self.db.execute(select(Course.tags).where(and_(*course_filter)))
        tag_counts: dict[str, int] = {}
        for (tags,) in tag_rows.all():
            for tag in tags or []:
                tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
        skill_demand = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

        demand_map = dict(demand)
        scored: list[tuple[float, dict[str, Any]]] = [
            (
                round(demand_map.get(cat, 0) / info["courses"], 2),
                {"category": cat, "courses": info["courses"]},
            )
            for cat, info in supply.items()
            if info["courses"]
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        opportunities = [{**meta, "enrollments_per_course": score} for score, meta in scored[:5]]

        return {
            "trending_topics": [{"category": cat, "enrollments": n} for cat, n in demand[:10]],
            "skill_demand": [{"skill": tag, "courses": n} for tag, n in skill_demand],
            "pricing_insights": dict(supply),
            "competition_analysis": {cat: info["courses"] for cat, info in supply.items()},
            "growth_opportunities": opportunities,
            "window_days": days,
        }
