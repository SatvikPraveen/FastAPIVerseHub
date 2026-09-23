# File: app/tests/test_services.py
"""Service-layer behaviour against the in-memory database."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.user import FileUpload, User
from app.schemas.course import CourseCreate, CourseUpdate
from app.schemas.user import UserUpdate
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.course_service import CourseService
from app.services.file_service import FileService
from app.services.token_service import TokenService
from app.services.user_service import UserService
from app.tests.conftest import UserFactory


class TestUserService:
    async def test_queries_and_counts(self, db_session: AsyncSession, test_user: User):
        service = UserService(db_session)
        await UserFactory.create_user(
            db_session, email="b@example.com", full_name="Bea", is_active=False
        )
        await UserFactory.create_user(
            db_session, email="c@example.com", full_name="Cy", is_verified=False
        )

        users, total = await service.get_users(search_query="example", sort_by="email", order="asc")
        assert total == 3 and [u.email for u in users][:2] == ["b@example.com", "c@example.com"]
        _, active_total = await service.get_users(is_active_filter=True)
        assert active_total == 2
        assert await service.count_users_by_status() == {
            "total": 3,
            "active": 2,
            "inactive": 1,
            "verified": 2,
        }
        assert [
            u.email for u in await service.search_users("bea", filters={"is_active": False})
        ] == ["b@example.com"]
        assert await service.search_users("zzz") == []

    async def test_activation_preferences_and_profile(self, db_session, test_user: User):
        service = UserService(db_session)
        assert await service.deactivate_user(test_user.id)
        assert not (await service.get_user_by_id(test_user.id)).is_active
        assert await service.activate_user(test_user.id)
        assert not await service.activate_user(999_999)

        updated = await service.update_user_preferences(
            test_user.id, {"skill_level": "advanced", "nonexistent": 1}
        )
        assert updated.skill_level == "advanced"
        profile = await service.get_user_learning_profile(test_user.id)
        assert profile["skill_level"] == "advanced"
        assert await service.get_user_learning_profile(999) == {}
        assert [u.id for u in await service.get_users_by_skill_level("advanced")] == [test_user.id]

        await service.update_user_activity(test_user.id)
        assert [u.id for u in await service.get_recently_active_users(days=1)] == [test_user.id]

        with pytest.raises(ValueError):
            await service.update_user(999, UserUpdate(full_name="x"))
        with pytest.raises(ValueError):
            await service.update_user_preferences(999, {})

    async def test_stats_and_soft_delete(self, db_session, test_user: User, test_course: Course):
        service = UserService(db_session)
        db_session.add(
            Enrollment(
                user_id=test_user.id, course_id=test_course.id, status=EnrollmentStatus.COMPLETED
            )
        )
        db_session.add(
            FileUpload(
                user_id=test_user.id,
                filename="f",
                original_filename="f",
                file_path="/f",
                file_size=1,
            )
        )
        await db_session.commit()
        stats = await service.get_user_stats(test_user.id)
        assert stats["completed_courses"] == 1 and stats["total_uploads"] == 1
        assert stats["account_age_days"] >= 0
        assert await service.get_user_stats(999) == {}

        assert await service.delete_user(test_user.id)
        assert await service.get_user_by_id(test_user.id) is None
        assert await service.get_user_by_email(test_user.email) is None


class TestCourseService:
    async def test_crud_and_filters(self, db_session, test_user: User):
        service = CourseService(db_session)
        create = CourseCreate(
            title="Async Python",
            category="programming",
            difficulty="advanced",
            price=Decimal("20.00"),
            original_price=Decimal("30.00"),
            is_free=False,
            tags=["py"],
        )
        course = await service.create_course(create, instructor_id=test_user.id)
        assert course.slug.startswith("async-python")
        assert await service.get_course_by_slug(course.slug) is not None

        # a second course with the same title gets a distinct slug
        again = await service.create_course(create, instructor_id=test_user.id)
        assert again.slug != course.slug

        updated = await service.update_course(course.id, CourseUpdate(title="Async Python 2"))
        assert updated.title == "Async Python 2"

        published = await service.publish_course(course.id)
        assert published.is_published and published.published_at is not None
        assert published.status.value == "published"
        unpublished = await service.unpublish_course(course.id)
        assert not unpublished.is_published

        await service.publish_course(course.id)
        courses, total = await service.get_courses(
            search_query="Async",
            category_filter="programming",
            difficulty_filter="advanced",
            is_published_filter=True,
            sort_by="title",
            order="desc",
        )
        assert total == 1 and courses[0].id == course.id
        assert (await service.get_courses(category_filter="nope"))[1] == 0
        categories = await service.get_categories()
        assert categories[0]["name"] == "programming"

        assert await service.delete_course(course.id)
        assert not await service.delete_course(course.id)
        with pytest.raises(ValueError):
            await service.publish_course(999)

    async def test_enrollments_and_stats(self, db_session, test_user, test_course):
        service = CourseService(db_session)
        student = await UserFactory.create_user(db_session, email="s@example.com")
        enrollment = await service.enroll_user(test_course.id, student.id)
        assert enrollment.status == EnrollmentStatus.ACTIVE
        assert await service.is_user_enrolled(test_course.id, student.id)

        rows, total = await service.get_course_enrollments(test_course.id)
        assert total == 1 and rows[0]["user_email"] == "s@example.com"
        stats = await service.get_course_stats(test_course.id)
        assert stats["total_enrollments"] == 1 and stats["completed_enrollments"] == 0

        await service.unenroll_user(test_course.id, student.id)
        assert not await service.is_user_enrolled(test_course.id, student.id)


class TestFileService:
    async def test_records_and_aggregates(self, db_session, test_user: User):
        service = FileService(db_session)
        a = await service.create_file_record(
            "a.pdf",
            "a.pdf",
            "/x/a.pdf",
            100,
            "application/pdf",
            test_user.id,
            category="docs",
            is_public=True,
        )
        b = await service.create_file_record(
            "b.png", "b.png", "/x/b.png", 50, "image/png", test_user.id, category="images"
        )
        await service.increment_download_count(a.id)
        await service.increment_download_count(a.id)

        files, total = await service.get_user_files(test_user.id, category="docs")
        assert total == 1 and files[0].id == a.id
        assert await service.get_categories_with_counts(test_user.id) == [
            {"name": "docs", "count": 1},
            {"name": "images", "count": 1},
        ]
        stats = await service.get_user_file_stats(test_user.id)
        assert stats == {
            "total_files": 2,
            "total_size_bytes": 150,
            "public_files": 1,
            "private_files": 1,
            "total_downloads": 2,
            "categories": {"docs": 1, "images": 1},
        }

        assert await service.update_file_metadata(b.id, test_user.id, description="d") is not None
        assert await service.update_file_metadata(b.id, 999, description="d") is None
        assert await service.update_file_info(999) is None
        assert await service.delete_file(b.id, test_user.id)
        assert await service.get_file_by_id(b.id) is None
        assert (await service.get_user_file_stats(test_user.id))["total_files"] == 1


class TestAnalyticsAndTokens:
    async def test_course_analytics_shape(self, db_session, test_course):
        analytics = await AnalyticsService(db_session).get_course_analytics(test_course.id, "7d")
        assert analytics["course_id"] == test_course.id
        assert analytics["total_enrollments"] == 0

    async def test_market_trends_empty_catalogue(self, db_session):
        trends = await AnalyticsService(db_session).get_market_trends(category="none")
        assert trends["trending_topics"] == [] and trends["growth_opportunities"] == []

    async def test_active_session_count(self, db_session, test_user):
        tokens = TokenService(db_session)
        await tokens.issue_pair(test_user)
        await tokens.issue_pair(test_user)
        assert await tokens.active_session_count(test_user.id) == 2
        assert await tokens.revoke_all_for_user(test_user.id) == 2
        assert await tokens.active_session_count(test_user.id) == 0
        assert await tokens.revoke_family(None) == 0
        assert await tokens.revoke_refresh_token("garbage", test_user.id) is False


class TestAuthService:
    async def test_mfa_lifecycle(self, db_session, mock_redis, test_user: User):
        service = AuthService(db_session, redis=mock_redis)
        assert await service.get_mfa_setup(test_user.id) is None
        await service.setup_mfa(test_user.id, "SECRET", ["code1", "code2"])
        assert (await service.get_mfa_setup(test_user.id))["secret"] == "SECRET"
        await service.enable_mfa(test_user.id, "SECRET", ["code1", "code2"])
        await db_session.refresh(test_user)
        assert test_user.mfa_enabled and test_user.backup_codes == ["code1", "code2"]
        assert await service.verify_backup_code(test_user.id, "code1")
        assert not await service.verify_backup_code(test_user.id, "code1")  # consumed
        assert not await service.verify_backup_code(999, "code1")
        await service.disable_mfa(test_user.id)
        await db_session.refresh(test_user)
        assert not test_user.mfa_enabled and test_user.mfa_secret is None

    async def test_devices_and_sessions(self, db_session, test_user: User):
        service = AuthService(db_session)
        device = await service.register_device(test_user.id, "Laptop", "desktop", "fp-1")
        assert device.device_token
        assert [d.id for d in await service.get_user_devices(test_user.id)] == [device.id]
        await service.revoke_device(test_user.id, device.id)
        assert await service.get_user_devices(test_user.id) == []

        session = await service.create_user_session(test_user.id, "sess-1", ip_address="1.1.1.1")
        listed = await service.get_user_sessions(test_user.id, None)
        assert listed[0]["session_id"] == session.session_id
        await service.revoke_session(test_user.id, "sess-1", None)
        assert await service.get_user_sessions(test_user.id, None) == []
        await service.create_user_session(test_user.id, "sess-2")
        assert await service.revoke_all_sessions(test_user.id, None) >= 1

    async def test_social_user_creation_and_password_change(self, db_session, test_user: User):
        service = AuthService(db_session)
        created = await service.get_or_create_social_user(
            provider="github", social_id="gh-1", email="social@example.com", full_name="Soc"
        )
        assert created.github_id == "gh-1" and created.is_verified
        existing = await service.get_or_create_social_user(
            provider="google", social_id="g-9", email=test_user.email
        )
        assert existing.id == test_user.id and existing.google_id == "g-9"

        await service.change_password(test_user.id, "NewPassw0rd!")
        assert await service.authenticate_user(test_user.email, "NewPassw0rd!") is not None
        assert await service.authenticate_user(test_user.email, "wrong") is None
        assert await service.authenticate_user("ghost@example.com", "x") is None
        await service.update_last_login(test_user.id)
        await db_session.refresh(test_user)
        assert test_user.login_count == 1
