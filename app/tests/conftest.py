# File: app/tests/conftest.py

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.dependencies import get_db, get_redis
from app.core.security import security_manager
from app.models.user import User, Base
from app.models.course import Course


# Test database URL (SQLite in-memory for fast testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    test_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestingSessionLocal() as session:
        yield session
    
    # Drop tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.ttl.return_value = 3600
    redis_mock.incrby.return_value = 1
    return redis_mock


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[TestClient, None]:
    """Create a test client with overridden dependencies."""
    
    def override_get_db():
        return db_session
    
    def override_get_redis():
        return mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    
    def override_get_db():
        return db_session
    
    def override_get_redis():
        return mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=security_manager.get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_verified=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        email="admin@example.com",
        hashed_password=security_manager.get_password_hash("adminpassword123"),
        full_name="Admin User",
        is_active=True,
        is_verified=True,
        is_superuser=True
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_course(db_session: AsyncSession, test_user: User) -> Course:
    """Create a test course."""
    course = Course(
        title="Test Course",
        slug="test-course-123",
        description="A test course for testing purposes",
        short_description="Test course",
        instructor_id=test_user.id,
        category="technology",
        difficulty="beginner",
        price=99.99,
        is_free=False,
        is_published=True
    )
    
    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)
    
    return course


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    access_token = security_manager.create_access_token(
        data={"sub": str(test_user.id), "email": test_user.email}
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_headers(test_superuser: User) -> dict:
    """Create authentication headers for admin user."""
    access_token = security_manager.create_access_token(
        data={
            "sub": str(test_superuser.id), 
            "email": test_superuser.email,
            "is_superuser": True
        }
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user registration data."""
    return {
        "email": "newuser@example.com",
        "password": "NewPassword123!",
        "confirm_password": "NewPassword123!",
        "full_name": "New User",
        "accept_terms": True
    }


@pytest.fixture
def sample_course_data() -> dict:
    """Sample course creation data."""
    return {
        "title": "New Test Course",
        "description": "A comprehensive course description",
        "short_description": "Short description",
        "category": "programming",
        "subcategory": "python",
        "difficulty": "intermediate",
        "estimated_duration_hours": 20,
        "language": "en",
        "tags": ["python", "programming", "beginners"],
        "learning_objectives": [
            "Learn Python basics",
            "Build real projects",
            "Understand best practices"
        ],
        "prerequisites": ["Basic computer skills"],
        "price": 149.99,
        "is_free": False
    }


@pytest.fixture
def mock_file():
    """Mock uploaded file."""
    from unittest.mock import Mock
    from io import BytesIO
    
    mock_file = Mock()
    mock_file.filename = "test.txt"
    mock_file.content_type = "text/plain"
    mock_file.size = 100
    mock_file.file = BytesIO(b"Test file content")
    mock_file.read = AsyncMock(return_value=b"Test file content")
    mock_file.seek = AsyncMock()
    
    return mock_file


@pytest.fixture
def mock_image_file():
    """Mock uploaded image file."""
    from unittest.mock import Mock
    from io import BytesIO
    
    mock_file = Mock()
    mock_file.filename = "test.jpg"
    mock_file.content_type = "image/jpeg"
    mock_file.size = 1024
    mock_file.file = BytesIO(b"fake image data")
    mock_file.read = AsyncMock(return_value=b"fake image data")
    mock_file.seek = AsyncMock()
    
    return mock_file


@pytest.fixture
def websocket_client():
    """WebSocket test client."""
    from fastapi.testclient import TestClient
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_email_service():
    """Mock email service."""
    from unittest.mock import Mock
    
    email_service = Mock()
    email_service.send_email = AsyncMock(return_value=True)
    email_service.send_welcome_email = AsyncMock(return_value=True)
    email_service.send_password_reset_email = AsyncMock(return_value=True)
    email_service.test_connection = AsyncMock(return_value=True)
    
    return email_service


@pytest.fixture
def mock_file_manager():
    """Mock file manager."""
    from unittest.mock import Mock
    
    file_manager = Mock()
    file_manager.validate_file = AsyncMock()
    file_manager.save_file = AsyncMock(return_value={
        "filename": "test_123.txt",
        "original_filename": "test.txt",
        "file_path": "/uploads/1/test_123.txt",
        "file_size": 100,
        "file_hash": "abc123",
        "content_type": "text/plain"
    })
    file_manager.delete_file = AsyncMock(return_value=True)
    file_manager.stream_file = AsyncMock()
    
    return file_manager


# Test data factories
class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create_user_data(**kwargs):
        """Create user data dictionary."""
        defaults = {
            "email": "factory@example.com",
            "password": "FactoryPassword123!",
            "confirm_password": "FactoryPassword123!",
            "full_name": "Factory User",
            "accept_terms": True
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    async def create_user(db_session: AsyncSession, **kwargs) -> User:
        """Create a user in the database."""
        data = UserFactory.create_user_data(**kwargs)
        
        user = User(
            email=data["email"],
            hashed_password=security_manager.get_password_hash(data["password"]),
            full_name=data["full_name"],
            is_active=data.get("is_active", True),
            is_verified=data.get("is_verified", True),
            is_superuser=data.get("is_superuser", False)
        )
        
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        return user


class CourseFactory:
    """Factory for creating test courses."""
    
    @staticmethod
    def create_course_data(**kwargs):
        """Create course data dictionary."""
        defaults = {
            "title": "Factory Course",
            "description": "A course created by factory",
            "category": "technology",
            "difficulty": "beginner",
            "price": 99.99,
            "is_free": False
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    async def create_course(db_session: AsyncSession, instructor_id: int, **kwargs) -> Course:
        """Create a course in the database."""
        data = CourseFactory.create_course_data(**kwargs)
        
        course = Course(
            title=data["title"],
            slug=f"factory-course-{datetime.now().timestamp()}",
            description=data["description"],
            instructor_id=instructor_id,
            category=data["category"],
            difficulty=data["difficulty"],
            price=data["price"],
            is_free=data["is_free"],
            is_published=data.get("is_published", True)
        )
        
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)
        
        return course


# Utility functions for tests
def assert_response_success(response, expected_status=200):
    """Assert response is successful."""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"


def assert_response_error(response, expected_status, expected_error_code=None):
    """Assert response is an error."""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}"
    
    if expected_error_code:
        data = response.json()
        assert data.get("error") == expected_error_code, f"Expected error code {expected_error_code}, got {data.get('error')}"


def assert_valid_token_response(response_data):
    """Assert token response structure is valid."""
    required_fields = ["access_token", "token_type"]
    
    for field in required_fields:
        assert field in response_data, f"Missing required field: {field}"
    
    assert response_data["token_type"] == "bearer"
    assert isinstance(response_data["access_token"], str)
    assert len(response_data["access_token"]) > 0


def create_test_token(user_id: int, **extra_data) -> str:
    """Create a test JWT token."""
    token_data = {"sub": str(user_id)}
    token_data.update(extra_data)
    
    return security_manager.create_access_token(data=token_data)