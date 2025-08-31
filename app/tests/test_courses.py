# File: app/tests/test_courses.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.course import Course
from app.tests.conftest import (
    assert_response_success,
    assert_response_error,
    UserFactory,
    CourseFactory
)


class TestCourseCreation:
    """Test course creation endpoints."""
    
    async def test_create_course_success(
        self, 
        async_client: AsyncClient, 
        sample_course_data, 
        auth_headers
    ):
        """Test successful course creation."""
        response = await async_client.post(
            "/api/v1/courses/", 
            json=sample_course_data,
            headers=auth_headers
        )
        
        assert_response_success(response, 201)
        data = response.json()
        
        assert data["title"] == sample_course_data["title"]
        assert data["category"] == sample_course_data["category"]
        assert data["difficulty"] == sample_course_data["difficulty"]
        assert "slug" in data
        assert data["is_published"] is False  # Default state
    
    async def test_create_course_unauthorized(
        self, 
        async_client: AsyncClient, 
        sample_course_data
    ):
        """Test course creation without authentication."""
        response = await async_client.post("/api/v1/courses/", json=sample_course_data)
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_create_course_invalid_data(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test course creation with invalid data."""
        invalid_data = {
            "title": "",  # Empty title
            "category": "",  # Empty category
        }
        
        response = await async_client.post(
            "/api/v1/courses/", 
            json=invalid_data,
            headers=auth_headers
        )
        
        assert_response_error(response, 422)
    
    async def test_create_course_with_pricing(
        self, 
        async_client: AsyncClient, 
        sample_course_data, 
        auth_headers
    ):
        """Test course creation with pricing information."""
        sample_course_data.update({
            "price": 199.99,
            "original_price": 299.99,
            "is_free": False
        })
        
        response = await async_client.post(
            "/api/v1/courses/", 
            json=sample_course_data,
            headers=auth_headers
        )
        
        assert_response_success(response, 201)
        data = response.json()
        
        assert float(data["price"]) == 199.99
        assert float(data["original_price"]) == 299.99
        assert data["is_free"] is False


class TestCourseRetrieval:
    """Test course retrieval endpoints."""
    
    async def test_get_courses_list(self, async_client: AsyncClient, test_course: Course):
        """Test getting list of courses."""
        response = await async_client.get("/api/v1/courses/")
        
        assert_response_success(response)
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
        
        # Check if test course is in the list
        course_ids = [course["id"] for course in data["items"]]
        assert test_course.id in course_ids
    
    async def test_get_courses_with_pagination(
        self, 
        async_client: AsyncClient, 
        db_session: AsyncSession,
        test_user: User
    ):
        """Test course list with pagination."""
        # Create multiple courses
        for i in range(5):
            await CourseFactory.create_course(
                db_session, 
                test_user.id, 
                title=f"Course {i}",
                is_published=True
            )
        
        response = await async_client.get("/api/v1/courses/?skip=2&limit=2")
        
        assert_response_success(response)
        data = response.json()
        
        assert len(data["items"]) <= 2
        assert data["skip"] == 2
        assert data["limit"] == 2
    
    async def test_get_courses_with_filters(
        self, 
        async_client: AsyncClient, 
        test_course: Course
    ):
        """Test course list with category filter."""
        response = await async_client.get(f"/api/v1/courses/?category={test_course.category}")
        
        assert_response_success(response)
        data = response.json()
        
        for course in data["items"]:
            assert course["category"] == test_course.category
    
    async def test_get_course_by_id(self, async_client: AsyncClient, test_course: Course):
        """Test getting specific course by ID."""
        response = await async_client.get(f"/api/v1/courses/{test_course.id}")
        
        assert_response_success(response)
        data = response.json()
        
        assert data["id"] == test_course.id
        assert data["title"] == test_course.title
        assert "total_enrollments" in data
        assert "average_rating" in data
    
    async def test_get_course_not_found(self, async_client: AsyncClient):
        """Test getting nonexistent course."""
        response = await async_client.get("/api/v1/courses/999999")
        
        assert_response_error(response, 404, "NOT_FOUND")
    
    async def test_search_courses(self, async_client: AsyncClient, test_course: Course):
        """Test course search functionality."""
        response = await async_client.get(f"/api/v1/courses/?q={test_course.title[:4]}")
        
        assert_response_success(response)
        data = response.json()
        
        assert len(data["items"]) >= 1
        # Search should return courses matching the query
        found_course = next((c for c in data["items"] if c["id"] == test_course.id), None)
        assert found_course is not None


class TestCourseUpdating:
    """Test course update endpoints."""
    
    async def test_update_course_success(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        auth_headers
    ):
        """Test successful course update."""
        update_data = {
            "title": "Updated Course Title",
            "description": "Updated description",
            "price": 149.99
        }
        
        response = await async_client.put(
            f"/api/v1/courses/{test_course.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["title"] == update_data["title"]
        assert data["description"] == update_data["description"]
        assert float(data["price"]) == update_data["price"]
    
    async def test_update_course_unauthorized(
        self, 
        async_client: AsyncClient, 
        test_course: Course
    ):
        """Test course update without authentication."""
        update_data = {"title": "Unauthorized Update"}
        
        response = await async_client.put(
            f"/api/v1/courses/{test_course.id}",
            json=update_data
        )
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_update_course_not_owner(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        db_session: AsyncSession
    ):
        """Test course update by non-owner."""
        # Create different user
        other_user = await UserFactory.create_user(
            db_session, 
            email="other@example.com"
        )
        
        other_headers = {
            "Authorization": f"Bearer {create_test_token(other_user.id)}"
        }
        
        update_data = {"title": "Unauthorized Update"}
        
        response = await async_client.put(
            f"/api/v1/courses/{test_course.id}",
            json=update_data,
            headers=other_headers
        )
        
        assert_response_error(response, 403, "FORBIDDEN")
    
    async def test_update_course_not_found(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test updating nonexistent course."""
        update_data = {"title": "Updated Title"}
        
        response = await async_client.put(
            "/api/v1/courses/999999",
            json=update_data,
            headers=auth_headers
        )
        
        assert_response_error(response, 404, "NOT_FOUND")


class TestCourseDeletion:
    """Test course deletion endpoints."""
    
    async def test_delete_course_success(
        self, 
        async_client: AsyncClient, 
        db_session: AsyncSession,
        test_user: User,
        auth_headers
    ):
        """Test successful course deletion."""
        # Create a course to delete
        course_to_delete = await CourseFactory.create_course(
            db_session, 
            test_user.id, 
            title="Course to Delete"
        )
        
        response = await async_client.delete(
            f"/api/v1/courses/{course_to_delete.id}",
            headers=auth_headers
        )
        
        assert_response_success(response, 204)
    
    async def test_delete_course_unauthorized(
        self, 
        async_client: AsyncClient, 
        test_course: Course
    ):
        """Test course deletion without authentication."""
        response = await async_client.delete(f"/api/v1/courses/{test_course.id}")
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_delete_course_not_owner(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        db_session: AsyncSession
    ):
        """Test course deletion by non-owner."""
        other_user = await UserFactory.create_user(
            db_session, 
            email="other@example.com"
        )
        
        other_headers = {
            "Authorization": f"Bearer {create_test_token(other_user.id)}"
        }
        
        response = await async_client.delete(
            f"/api/v1/courses/{test_course.id}",
            headers=other_headers
        )
        
        assert_response_error(response, 403, "FORBIDDEN")


class TestCoursePublishing:
    """Test course publishing endpoints."""
    
    async def test_publish_course_success(
        self, 
        async_client: AsyncClient, 
        db_session: AsyncSession,
        test_user: User,
        auth_headers
    ):
        """Test successful course publishing."""
        # Create unpublished course
        unpublished_course = await CourseFactory.create_course(
            db_session, 
            test_user.id, 
            is_published=False
        )
        
        response = await async_client.post(
            f"/api/v1/courses/{unpublished_course.id}/publish",
            headers=auth_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["is_published"] is True
        assert data["status"] == "published"
    
    async def test_unpublish_course_success(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        auth_headers
    ):
        """Test successful course unpublishing."""
        response = await async_client.post(
            f"/api/v1/courses/{test_course.id}/unpublish",
            headers=auth_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["is_published"] is False
        assert data["status"] == "draft"
    
    async def test_publish_already_published_course(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        auth_headers
    ):
        """Test publishing already published course."""
        response = await async_client.post(
            f"/api/v1/courses/{test_course.id}/publish",
            headers=auth_headers
        )
        
        assert_response_error(response, 400, "BAD_REQUEST")


class TestCourseEnrollment:
    """Test course enrollment endpoints."""
    
    async def test_enroll_in_course_success(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        db_session: AsyncSession
    ):
        """Test successful course enrollment."""
        # Create a different user to enroll
        student = await UserFactory.create_user(
            db_session, 
            email="student@example.com"
        )
        
        student_headers = {
            "Authorization": f"Bearer {create_test_token(student.id)}"
        }
        
        response = await async_client.post(
            f"/api/v1/courses/{test_course.id}/enroll",
            headers=student_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert "enrolled" in data["message"].lower()
        assert data["course_id"] == test_course.id
        assert data["user_id"] == student.id
    
    async def test_enroll_in_unpublished_course(
        self, 
        async_client: AsyncClient, 
        db_session: AsyncSession,
        test_user: User
    ):
        """Test enrollment in unpublished course."""
        # Create unpublished course
        unpublished_course = await CourseFactory.create_course(
            db_session, 
            test_user.id, 
            is_published=False
        )
        
        student = await UserFactory.create_user(
            db_session, 
            email="student@example.com"
        )
        
        student_headers = {
            "Authorization": f"Bearer {create_test_token(student.id)}"
        }
        
        response = await async_client.post(
            f"/api/v1/courses/{unpublished_course.id}/enroll",
            headers=student_headers
        )
        
        assert_response_error(response, 400, "BAD_REQUEST")
    
    async def test_unenroll_from_course_success(
        self, 
        async_client: AsyncClient, 
        test_course: Course, 
        db_session: AsyncSession
    ):
        """Test successful course unenrollment."""
        student = await UserFactory.create_user(
            db_session, 
            email="student@example.com"
        )
        
        student_headers = {
            "Authorization": f"Bearer {create_test_token(student.id)}"
        }
        
        # First enroll
        await async_client.post(
            f"/api/v1/courses/{test_course.id}/enroll",
            headers=student_headers
        )
        
        # Then unenroll
        response = await async_client.delete(
            f"/api/v1/courses/{test_course.id}/enroll",
            headers=student_headers
        )
        
        assert_response_success(response)
        data = response.json()
        
        assert "unenrolled" in data["message"].lower()


class TestCourseCategories:
    """Test course category endpoints."""
    
    async def test_get_course_categories(
        self, 
        async_client: AsyncClient, 
        test_course: Course
    ):
        """Test getting course categories."""
        response = await async_client.get("/api/v1/courses/categories/")
        
        assert_response_success(response)
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check structure of category data
        for category in data:
            assert "name" in category
            assert "count" in category
            assert isinstance(category["count"], int)


# Helper function
def create_test_token(user_id: int) -> str:
    """Create test token for authentication."""
    from app.core.security import security_manager
    return security_manager.create_access_token(data={"sub": str(user_id)})