# File: app/services/advanced_course_service.py
"""Advanced course operations: learning profiles, cohorts, A/B experiments, bulk ops."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.course import (
    Course,
    CourseExperiment,
    CourseReview,
    Enrollment,
    EnrollmentStatus,
    ExperimentStatus,
)
from app.models.user import User

# Fields an instructor may change through the bulk endpoint.
BULK_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "category",
        "subcategory",
        "language",
        "price",
        "original_price",
        "currency",
        "is_free",
        "is_published",
        "is_featured",
        "difficulty",
        "tags",
    }
)


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


@dataclass
class Cohort:
    """Students who enrolled in the same calendar month."""

    id: str
    start_date: datetime
    student_count: int
    completion_rate: float
    avg_progress: float
    avg_rating: float | None
    performance_metrics: dict[str, Any]


class AdvancedCourseService:
    """Service for advanced course operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # User learning profile
    # ------------------------------------------------------------------

    async def get_user_learning_profile(self, user_id: int) -> dict[str, Any]:
        """Aggregate learning history and preferences for a user."""
        user = await self.db.get(User, user_id)
        if not user:
            return {}

        completed = (
            await self.db.execute(
                select(func.count(Enrollment.id)).where(
                    and_(
                        Enrollment.user_id == user_id,
                        Enrollment.status == EnrollmentStatus.COMPLETED,
                    )
                )
            )
        ).scalar() or 0

        return {
            "user_id": user_id,
            "interests": user.interests or [],
            "learning_style": user.learning_style,
            "skill_level": user.skill_level,
            "average_skill_level": user.skill_level,
            "completed_courses": int(completed),
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
        """Curated learning paths built from the published catalogue.

        Paths are derived per category: courses are ordered by difficulty so
        the sequence beginner -> expert forms a natural progression.
        """
        query = select(Course).where(Course.is_published.is_(True))
        if category:
            query = query.where(Course.category == category)
        courses = list((await self.db.execute(query.order_by(Course.category))).scalars().all())

        order = {"beginner": 0, "intermediate": 1, "advanced": 2, "expert": 3}
        by_category: dict[str, list[Course]] = {}
        for course in courses:
            by_category.setdefault(course.category, []).append(course)

        paths: list[LearningPath] = []
        for idx, (cat, items) in enumerate(sorted(by_category.items()), start=1):
            items.sort(key=lambda c: order.get(str(c.difficulty), 0))
            hours = sum(c.estimated_duration_hours or 0 for c in items)
            path_difficulty = str(items[-1].difficulty) if items else "beginner"
            if difficulty and path_difficulty != difficulty:
                continue
            paths.append(
                LearningPath(
                    id=idx,
                    title=f"{cat.title()} Path",
                    description=f"A progressive path through {len(items)} {cat} courses.",
                    courses=[
                        {
                            "id": c.id,
                            "title": c.title,
                            "order": i,
                            "estimated_hours": c.estimated_duration_hours or 0,
                        }
                        for i, c in enumerate(items, start=1)
                    ],
                    estimated_duration_weeks=max(1, math.ceil(hours / 5)) if hours else 4,
                    difficulty=path_difficulty,
                )
            )
        return paths

    async def save_learning_path(
        self, user_id: int, learning_path_data: dict[str, Any]
    ) -> LearningPath:
        """Materialise a generated learning path (in-memory representation)."""
        return LearningPath(
            id=int(learning_path_data.get("id", 1)),
            title=learning_path_data.get("title", "Custom Learning Path"),
            description=learning_path_data.get("description", ""),
            courses=learning_path_data.get("courses", []),
            estimated_duration_weeks=int(learning_path_data.get("estimated_duration_weeks", 4)),
            difficulty=learning_path_data.get("difficulty_preference", "intermediate"),
        )

    async def send_learning_path_notification(self, user_id: int, path_id: int) -> None:
        """Background task hook: notify a user about their new learning path."""

    # ------------------------------------------------------------------
    # Course helpers
    # ------------------------------------------------------------------

    async def get_course_by_id(self, course_id: int) -> Course | None:
        return await self.db.get(Course, course_id)

    async def get_course_performance_data(
        self, course_id: int, time_range: str = "30d"
    ) -> dict[str, Any]:
        """Aggregated enrollment/completion data for a course."""
        row = (
            await self.db.execute(
                select(
                    func.count(Enrollment.id),
                    func.count(Enrollment.id).filter(
                        Enrollment.status == EnrollmentStatus.COMPLETED
                    ),
                    func.avg(Enrollment.progress_percentage),
                ).where(Enrollment.course_id == course_id)
            )
        ).one()
        total, completed, avg_progress = int(row[0] or 0), int(row[1] or 0), float(row[2] or 0)
        return {
            "course_id": course_id,
            "total_enrollments": total,
            "completed": completed,
            "completion_rate": (completed / total * 100) if total else 0.0,
            "average_progress": round(avg_progress, 2),
            "time_range": time_range,
        }

    async def save_optimization_report(
        self, course_id: int, user_id: int, optimization_results: dict[str, Any]
    ) -> str:
        """Persist an optimisation report and return its identifier.

        Reports are stored as a JSON payload on the course's ``course_outline``
        metadata bucket to avoid a dedicated table for what is advisory data.
        """
        report_id = uuid.uuid4().hex
        course = await self.get_course_by_id(course_id)
        if course is not None:
            outline = dict(course.course_outline or {})
            reports = list(outline.get("optimization_reports", []))[-9:]  # keep last 10
            reports.append(
                {
                    "id": report_id,
                    "requested_by": user_id,
                    "created_at": utcnow().isoformat(),
                    "score": optimization_results.get("score"),
                    "suggestions": optimization_results.get("suggestions", []),
                }
            )
            outline["optimization_reports"] = reports
            course.course_outline = outline
            await self.db.commit()
        return report_id

    async def apply_optimization_suggestions(
        self, course_id: int, suggestions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Background task: apply machine-applicable suggestions (advisory only today)."""
        return {"course_id": course_id, "applied": len(suggestions), "status": "queued"}

    # ------------------------------------------------------------------
    # Cohorts
    # ------------------------------------------------------------------

    async def get_course_cohorts(
        self, course_id: int, skip: int = 0, limit: int = 20
    ) -> list[Cohort]:
        """Group a course's enrollments into monthly cohorts."""
        rows = (
            await self.db.execute(
                select(Enrollment)
                .where(Enrollment.course_id == course_id)
                .order_by(Enrollment.enrolled_at)
            )
        ).scalars()
        buckets: dict[str, list[Enrollment]] = {}
        for enrollment in rows:
            key = enrollment.enrolled_at.strftime("%Y-%m")
            buckets.setdefault(key, []).append(enrollment)

        avg_rating = (
            await self.db.execute(
                select(func.avg(CourseReview.rating)).where(CourseReview.course_id == course_id)
            )
        ).scalar()

        cohorts: list[Cohort] = []
        for key, members in sorted(buckets.items()):
            completed = sum(1 for m in members if m.status == EnrollmentStatus.COMPLETED)
            dropped = sum(1 for m in members if m.status == EnrollmentStatus.DROPPED)
            cohorts.append(
                Cohort(
                    id=key,
                    start_date=min(m.enrolled_at for m in members),
                    student_count=len(members),
                    completion_rate=round(completed / len(members) * 100, 2),
                    avg_progress=round(
                        sum(float(m.progress_percentage or 0) for m in members) / len(members), 2
                    ),
                    avg_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
                    performance_metrics={
                        "completed": completed,
                        "dropped": dropped,
                        "active": len(members) - completed - dropped,
                        "avg_time_spent_minutes": round(
                            sum(m.total_time_spent_minutes or 0 for m in members) / len(members)
                        ),
                    },
                )
            )
        return cohorts[skip : skip + limit]

    # ------------------------------------------------------------------
    # A/B experiments
    # ------------------------------------------------------------------

    async def create_ab_experiment(
        self, course_id: int, instructor_id: int, config: dict[str, Any]
    ) -> CourseExperiment:
        """Create and start an experiment from a client-supplied config."""
        raw_variants = config.get("variants") or [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ]
        variants = [
            {
                "name": str(v.get("name", f"variant_{i}")),
                "weight": float(v.get("weight", 1 / len(raw_variants))),
                "exposures": int(v.get("exposures", 0)),
                "conversions": int(v.get("conversions", 0)),
                "changes": v.get("changes", {}),
            }
            for i, v in enumerate(raw_variants)
        ]
        experiment = CourseExperiment(
            course_id=course_id,
            instructor_id=instructor_id,
            name=str(config.get("name", "Untitled experiment")),
            hypothesis=config.get("hypothesis"),
            status=ExperimentStatus.RUNNING,
            variants=variants,
            success_metrics=list(config.get("success_metrics", ["conversion_rate"])),
            estimated_duration_days=int(config.get("estimated_duration_days", 14)),
            start_date=utcnow(),
        )
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        return experiment

    async def get_experiment(self, experiment_id: int) -> CourseExperiment | None:
        return await self.db.get(CourseExperiment, experiment_id)

    async def record_exposure(
        self, experiment_id: int, variant_name: str, converted: bool = False
    ) -> bool:
        """Increment a variant's counters (used by the serving layer)."""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            return False
        variants = [dict(v) for v in experiment.variants]
        for v in variants:
            if v["name"] == variant_name:
                v["exposures"] = int(v.get("exposures", 0)) + 1
                if converted:
                    v["conversions"] = int(v.get("conversions", 0)) + 1
                break
        else:
            return False
        experiment.variants = variants
        await self.db.commit()
        return True

    async def get_experiment_results(self, experiment_id: int) -> dict[str, Any]:
        """Two-proportion z-test of every variant against the first (control)."""
        experiment = await self.get_experiment(experiment_id)
        if experiment is None:
            return {
                "statistical_significance": False,
                "winning_variant": None,
                "confidence_level": 0.0,
                "variant_performance": [],
                "recommendations": [],
            }

        performance = []
        for v in experiment.variants:
            exposures = int(v.get("exposures", 0))
            conversions = int(v.get("conversions", 0))
            performance.append(
                {
                    "name": v["name"],
                    "exposures": exposures,
                    "conversions": conversions,
                    "conversion_rate": round(conversions / exposures, 4) if exposures else 0.0,
                }
            )

        control = performance[0] if performance else None
        best = max(performance, key=lambda p: p["conversion_rate"], default=None)
        confidence = 0.0
        if control and best and best is not control:
            confidence = _two_proportion_confidence(
                control["conversions"], control["exposures"], best["conversions"], best["exposures"]
            )
        significant = confidence >= 0.95

        recommendations: list[str] = []
        if not performance or all(p["exposures"] == 0 for p in performance):
            recommendations.append("No exposures recorded yet; keep the experiment running.")
        elif significant and best:
            recommendations.append(f"Roll out '{best['name']}' to all students.")
        else:
            recommendations.append("Difference is not yet significant; collect more data.")

        return {
            "statistical_significance": significant,
            "winning_variant": best["name"] if significant and best else None,
            "confidence_level": round(confidence, 4),
            "variant_performance": performance,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def validate_instructor_courses(
        self, course_ids: list[int], instructor_id: int
    ) -> list[int]:
        """Return the subset of ``course_ids`` owned by ``instructor_id``."""
        if not course_ids:
            return []
        rows = await self.db.execute(
            select(Course.id).where(
                and_(Course.id.in_(course_ids), Course.instructor_id == instructor_id)
            )
        )
        return [int(cid) for cid in rows.scalars().all()]

    async def bulk_update_courses(
        self, course_ids: list[int], updates: dict[str, Any], user_id: int
    ) -> int:
        """Apply whitelisted field updates to many courses in one statement."""
        safe_updates = {k: v for k, v in updates.items() if k in BULK_UPDATABLE_FIELDS}
        if not safe_updates or not course_ids:
            return 0
        safe_updates["last_updated_at"] = utcnow()
        result = await self.db.execute(
            update(Course)
            .where(and_(Course.id.in_(course_ids), Course.instructor_id == user_id))
            .values(**safe_updates)
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)


def _two_proportion_confidence(c1: int, n1: int, c2: int, n2: int) -> float:
    """Confidence (1 - p) that two conversion rates differ, via a pooled z-test."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = c1 / n1, c2 / n2
    pooled = (c1 + c2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0
    z = abs(p1 - p2) / se
    # two-sided p-value from the normal CDF
    p_value = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return max(0.0, min(1.0, 1 - p_value))
