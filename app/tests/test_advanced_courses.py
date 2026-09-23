# File: app/tests/test_advanced_courses.py
"""v2 course analytics, cohorts, experiments and bulk operations."""

from datetime import timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.course import Course, CourseReview, Enrollment, EnrollmentStatus
from app.services.advanced_course_service import AdvancedCourseService
from app.tests.conftest import CourseFactory, UserFactory


async def _seed_enrollments(db: AsyncSession, course: Course, count: int = 6) -> None:
    now = utcnow()
    for i in range(count):
        student = await UserFactory.create_user(db, email=f"student{i}@example.com")
        status = EnrollmentStatus.COMPLETED if i % 3 == 0 else EnrollmentStatus.ACTIVE
        db.add(
            Enrollment(
                user_id=student.id,
                course_id=course.id,
                status=status,
                progress_percentage=Decimal("100.00")
                if status.value == "completed"
                else Decimal("40.00"),
                enrolled_at=now - timedelta(days=40 * (i % 2)),  # two monthly cohorts
                payment_amount=course.price,
                total_time_spent_minutes=30 * i,
            )
        )
        if status == EnrollmentStatus.COMPLETED:
            db.add(CourseReview(user_id=student.id, course_id=course.id, rating=4 + (i % 2)))
    await db.commit()


class TestRecommendationsAndPaths:
    async def test_recommendations(self, async_client: AsyncClient, auth_headers):
        response = await async_client.get(
            "/api/v2/courses/recommendations",
            params={"limit": 3, "include_reasoning": True},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["recommendations"]) == 3
        assert body["recommendations"][0]["reasoning"]

        custom = await async_client.post(
            "/api/v2/courses/recommendations/custom",
            json={
                "interests": ["python"],
                "skill_level": "beginner",
                "learning_goals": ["job"],
                "time_commitment_hours": 5,
                "preferred_formats": ["video"],
            },
            headers=auth_headers,
        )
        assert custom.status_code == 200
        assert custom.json()["total_found"] == len(custom.json()["recommendations"])

    async def test_learning_paths_are_derived_from_catalogue(
        self, async_client: AsyncClient, auth_headers, test_user, db_session
    ):
        for difficulty in ("beginner", "advanced"):
            await CourseFactory.create_course(
                db_session, instructor_id=test_user.id, category="data", difficulty=difficulty
            )
        response = await async_client.get(
            "/api/v2/courses/learning-paths", params={"category": "data"}, headers=auth_headers
        )
        assert response.status_code == 200
        paths = response.json()["learning_paths"]
        assert len(paths) == 1
        assert paths[0]["total_courses"] == 2 and paths[0]["difficulty"] == "advanced"

        none = await async_client.get(
            "/api/v2/courses/learning-paths", params={"difficulty": "expert"}, headers=auth_headers
        )
        assert none.json()["learning_paths"] == []

        created = await async_client.post(
            "/api/v2/courses/learning-paths/create",
            json={
                "goal": "backend",
                "current_skills": ["python"],
                "target_skills": ["fastapi"],
                "timeline_weeks": 6,
                "difficulty_preference": "intermediate",
            },
            headers=auth_headers,
        )
        assert created.status_code == 200
        assert created.json()["title"]


class TestAnalytics:
    async def test_course_analytics_owner_only(
        self, async_client: AsyncClient, auth_headers, admin_headers, test_course, db_session
    ):
        await _seed_enrollments(db_session, test_course)
        owner = await async_client.get(
            f"/api/v2/courses/analytics/{test_course.id}", headers=auth_headers
        )
        assert owner.status_code == 200, owner.text
        assert owner.json()["total_enrollments"] == 6

        stranger_headers = {
            "Authorization": admin_headers["Authorization"].replace("Bearer ", "Bearer x")
        }
        assert (
            await async_client.get(
                f"/api/v2/courses/analytics/{test_course.id}", headers=stranger_headers
            )
        ).status_code == 401
        assert (
            await async_client.get("/api/v2/courses/analytics/999999", headers=auth_headers)
        ).status_code == 404

    async def test_dashboard_and_market_trends(
        self, async_client: AsyncClient, auth_headers, test_course, db_session
    ):
        await _seed_enrollments(db_session, test_course)
        dashboard = await async_client.get(
            "/api/v2/courses/performance/dashboard", headers=auth_headers
        )
        assert dashboard.status_code == 200, dashboard.text
        overview = dashboard.json()["overview"]
        assert overview["total_courses"] == 1 and overview["total_students"] == 6
        assert overview["total_revenue"] > 0
        assert dashboard.json()["top_performing_courses"][0]["students"] == 6

        trends = await async_client.get("/api/v2/courses/trends/market")
        assert trends.status_code == 200
        body = trends.json()
        assert body["trending_topics"][0] == {"category": "technology", "enrollments": 6}
        assert "technology" in body["pricing_insights"]
        assert body["growth_opportunities"][0]["category"] == "technology"


class TestCohortsAndExperiments:
    async def test_cohorts(self, async_client: AsyncClient, auth_headers, test_course, db_session):
        await _seed_enrollments(db_session, test_course)
        response = await async_client.get(
            f"/api/v2/courses/cohorts/{test_course.id}", headers=auth_headers
        )
        assert response.status_code == 200, response.text
        cohorts = response.json()["cohorts"]
        assert len(cohorts) == 2
        assert sum(c["student_count"] for c in cohorts) == 6
        assert all(0 <= c["completion_rate"] <= 100 for c in cohorts)

    async def test_optimize_and_bulk_update(
        self, async_client: AsyncClient, auth_headers, test_course, db_session
    ):
        optimized = await async_client.post(
            f"/api/v2/courses/optimize/{test_course.id}",
            json={
                "course_id": test_course.id,
                "optimization_goals": ["completion_rate"],
                "target_metrics": {"completion_rate": 0.8},
            },
            headers=auth_headers,
        )
        assert optimized.status_code == 200, optimized.text
        assert optimized.json()["report_id"]
        await db_session.refresh(test_course)
        assert (
            test_course.course_outline["optimization_reports"][0]["id"]
            == optimized.json()["report_id"]
        )

        bulk = await async_client.post(
            "/api/v2/courses/bulk-operations/update",
            json={
                "course_ids": [test_course.id],
                "updates": {"is_featured": True, "hashed_password": "x"},
            },
            headers=auth_headers,
        )
        assert bulk.status_code == 200
        await db_session.refresh(test_course)
        assert test_course.is_featured is True

        forbidden = await async_client.post(
            "/api/v2/courses/bulk-operations/update",
            json={"course_ids": [test_course.id, 999999], "updates": {"is_featured": False}},
            headers=auth_headers,
        )
        assert forbidden.status_code == 403

    async def test_ab_experiment_lifecycle(
        self, async_client: AsyncClient, auth_headers, test_course, db_session
    ):
        created = await async_client.post(
            "/api/v2/courses/experiments/ab-test",
            params={"course_id": test_course.id},
            json={
                "name": "New thumbnail",
                "variants": [{"name": "control"}, {"name": "bold"}],
                "success_metrics": ["conversion_rate"],
                "estimated_duration_days": 7,
            },
            headers=auth_headers,
        )
        assert created.status_code == 200, created.text
        experiment_id = created.json()["experiment_id"]
        assert created.json()["status"] == "running"

        results = await async_client.get(
            f"/api/v2/courses/experiments/{experiment_id}/results", headers=auth_headers
        )
        assert results.json()["statistical_significance"] is False
        assert "keep the experiment running" in results.json()["recommendations"][0]

        service = AdvancedCourseService(db_session)
        for _ in range(100):
            await service.record_exposure(experiment_id, "control", converted=False)
            await service.record_exposure(experiment_id, "bold", converted=False)
        for _ in range(10):
            await service.record_exposure(experiment_id, "control", converted=True)
        for _ in range(35):
            await service.record_exposure(experiment_id, "bold", converted=True)
        assert await service.record_exposure(experiment_id, "missing") is False

        results = await async_client.get(
            f"/api/v2/courses/experiments/{experiment_id}/results", headers=auth_headers
        )
        body = results.json()
        assert body["statistical_significance"] is True
        assert body["winning_variant"] == "bold"
        assert body["confidence_level"] >= 0.95
        assert "Roll out 'bold'" in body["recommendations"][0]

        assert (
            await async_client.get("/api/v2/courses/experiments/999/results", headers=auth_headers)
        ).status_code == 404
