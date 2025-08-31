# Testing Guide

**File Location: `docs/testing_guide.md`**

## Testing Strategy Overview

This guide covers comprehensive testing strategies for the FastAPIVerseHub project, including unit tests, integration tests, and end-to-end testing approaches.

## Testing Stack

- **Testing Framework**: pytest
- **Async Testing**: pytest-asyncio
- **HTTP Client**: httpx (AsyncClient)
- **Database Testing**: SQLAlchemy with test database
- **Mocking**: unittest.mock + pytest-mock
- **Coverage**: pytest-cov
- **WebSocket Testing**: websockets + asyncio

## Project Test Structure

```
app/tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_auth.py            # Authentication tests
├── test_users.py           # User management tests
├── test_courses.py         # Course CRUD tests
├── test_uploads.py         # File upload tests
├── test_websockets.py      # WebSocket tests
├── test_sse.py             # Server-Sent Events tests
├── test_middleware.py      # Middleware tests
├── test_services.py        # Service layer tests
└── test_utils.py           # Utility function tests
```

## Test Configuration (conftest.py)

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_db
from app.core.config import settings
from app.models.base import Base
from app.models.user import User
from app.core.security import create_access_token

# Test database URL
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def setup_test_db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_test_db):
    """Create database session for testing"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def override_get_db(db_session):
    """Override database dependency"""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    return _override_get_db

@pytest_asyncio.fixture
async def async_client(db_session):
    """Async test client"""
    app.dependency_overrides[get_db] = override_get_db(db_session)
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Sample user data"""
    return {
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User"
    }

@pytest_asyncio.fixture
async def authenticated_client(async_client, db_session, test_user_data):
    """Authenticated test client"""
    # Create test user
    response = await async_client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201

    # Login to get token
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": test_user_data["email"], "password": test_user_data["password"]}
    )
    token = response.json()["access_token"]

    # Set authorization header
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    return async_client
```

## Unit Testing

### Testing Authentication

```python
# app/tests/test_auth.py
import pytest
from app.core.security import create_access_token, verify_password, hash_password

class TestAuthentication:

    @pytest.mark.asyncio
    async def test_user_registration(self, async_client):
        user_data = {
            "email": "newuser@example.com",
            "password": "securepass123",
            "full_name": "New User"
        }
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_user_login(self, async_client, test_user_data):
        # Register user first
        await async_client.post("/api/v1/auth/register", json=test_user_data)

        # Login
        response = await async_client.post(
            "/api/v1/auth/token",
            data={"username": test_user_data["email"], "password": test_user_data["password"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_invalid_login(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/token",
            data={"username": "invalid@example.com", "password": "wrongpass"}
        )
        assert response.status_code == 401

    def test_password_hashing(self):
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_token_creation(self):
        token = create_access_token(data={"sub": "user@example.com"})
        assert token is not None
        assert isinstance(token, str)
```

### Testing User Management

```python
# app/tests/test_users.py
import pytest

class TestUserManagement:

    @pytest.mark.asyncio
    async def test_get_current_user(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_update_current_user(self, authenticated_client):
        update_data = {"full_name": "Updated Name", "bio": "Updated bio"}
        response = await authenticated_client.put("/api/v1/users/me", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == update_data["full_name"]

    @pytest.mark.asyncio
    async def test_get_users_list(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/users/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, async_client):
        response = await async_client.get("/api/v1/users/me")
        assert response.status_code == 401
```

### Testing Course Management

```python
# app/tests/test_courses.py
import pytest

class TestCourseManagement:

    @pytest.fixture
    def course_data(self):
        return {
            "title": "Test Course",
            "description": "A test course description",
            "category": "Programming",
            "difficulty": "beginner",
            "estimated_duration": 120
        }

    @pytest.mark.asyncio
    async def test_create_course(self, authenticated_client, course_data):
        response = await authenticated_client.post("/api/v1/courses/", json=course_data)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == course_data["title"]
        assert data["category"] == course_data["category"]

    @pytest.mark.asyncio
    async def test_get_course(self, authenticated_client, course_data):
        # Create course
        response = await authenticated_client.post("/api/v1/courses/", json=course_data)
        course_id = response.json()["id"]

        # Get course
        response = await authenticated_client.get(f"/api/v1/courses/{course_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == course_id

    @pytest.mark.asyncio
    async def test_update_course(self, authenticated_client, course_data):
        # Create course
        response = await authenticated_client.post("/api/v1/courses/", json=course_data)
        course_id = response.json()["id"]

        # Update course
        update_data = {"title": "Updated Course Title"}
        response = await authenticated_client.put(f"/api/v1/courses/{course_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == update_data["title"]

    @pytest.mark.asyncio
    async def test_delete_course(self, authenticated_client, course_data):
        # Create course
        response = await authenticated_client.post("/api/v1/courses/", json=course_data)
        course_id = response.json()["id"]

        # Delete course
        response = await authenticated_client.delete(f"/api/v1/courses/{course_id}")
        assert response.status_code == 204

        # Verify deletion
        response = await authenticated_client.get(f"/api/v1/courses/{course_id}")
        assert response.status_code == 404
```

## Integration Testing

### Testing File Uploads

```python
# app/tests/test_uploads.py
import pytest
import io

class TestFileUploads:

    @pytest.mark.asyncio
    async def test_file_upload(self, authenticated_client):
        # Create test file
        file_content = b"This is test file content"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        data = {"description": "Test file upload"}

        response = await authenticated_client.post(
            "/api/v1/uploads/",
            files=files,
            data=data
        )
        assert response.status_code == 201
        result = response.json()
        assert result["filename"] == "test.txt"
        assert result["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_file_download(self, authenticated_client):
        # Upload file first
        file_content = b"Download test content"
        files = {"file": ("download_test.txt", io.BytesIO(file_content), "text/plain")}

        upload_response = await authenticated_client.post("/api/v1/uploads/", files=files)
        file_id = upload_response.json()["id"]

        # Download file
        response = await authenticated_client.get(f"/api/v1/uploads/{file_id}/download")
        assert response.status_code == 200
        assert response.content == file_content

    @pytest.mark.asyncio
    async def test_invalid_file_type(self, authenticated_client):
        # Try to upload invalid file type
        file_content = b"Invalid content"
        files = {"file": ("test.exe", io.BytesIO(file_content), "application/x-executable")}

        response = await authenticated_client.post("/api/v1/uploads/", files=files)
        assert response.status_code == 400
```

### Testing WebSockets

```python
# app/tests/test_websockets.py
import pytest
import asyncio
import json
from websockets import connect, ConnectionClosedError

class TestWebSockets:

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        uri = "ws://localhost:8000/api/v1/ws"
        try:
            async with connect(uri) as websocket:
                # Test connection
                await websocket.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                assert data["type"] == "pong"
        except ConnectionClosedError:
            pytest.skip("WebSocket server not running")

    @pytest.mark.asyncio
    async def test_websocket_authentication(self, test_user_data):
        # Create token for authentication
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": test_user_data["email"]})

        uri = "ws://localhost:8000/api/v1/ws"
        try:
            async with connect(uri) as websocket:
                # Authenticate
                auth_message = {"type": "authenticate", "token": token}
                await websocket.send(json.dumps(auth_message))

                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                assert data["type"] == "authenticated"
        except ConnectionClosedError:
            pytest.skip("WebSocket server not running")
```

### Testing Server-Sent Events

```python
# app/tests/test_sse.py
import pytest
import asyncio

class TestServerSentEvents:

    @pytest.mark.asyncio
    async def test_sse_connection(self, authenticated_client):
        # Test SSE endpoint
        response = await authenticated_client.get("/api/v1/sse/notifications")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

    @pytest.mark.asyncio
    async def test_sse_events(self):
        # This would require a more complex setup to test actual event streaming
        # For now, we test that the endpoint is accessible
        pass
```

## Service Layer Testing

```python
# app/tests/test_services.py
import pytest
from unittest.mock import AsyncMock, Mock
from app.services.user_service import UserService
from app.services.auth_service import AuthService

class TestUserService:

    @pytest.mark.asyncio
    async def test_create_user(self):
        mock_db = AsyncMock()
        mock_user = Mock()
        mock_user.id = 1
        mock_user.email = "test@example.com"

        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = UserService()
        user_data = {
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }

        # Mock the user creation
        with pytest.mock.patch('app.models.user.User', return_value=mock_user):
            result = await service.create_user(mock_db, user_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_email(self):
        mock_db = AsyncMock()
        mock_query_result = Mock()
        mock_user = Mock()
        mock_user.email = "test@example.com"

        mock_query_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_query_result

        service = UserService()
        result = await service.get_user_by_email(mock_db, "test@example.com")

        assert result == mock_user
        mock_db.execute.assert_called_once()
```

## Testing Middleware

```python
# app/tests/test_middleware.py
import pytest
import time
from unittest.mock import Mock

class TestMiddleware:

    @pytest.mark.asyncio
    async def test_request_timing_middleware(self, async_client):
        response = await async_client.get("/health")
        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time > 0

    @pytest.mark.asyncio
    async def test_cors_middleware(self, async_client):
        response = await async_client.options("/api/v1/users/")
        assert "Access-Control-Allow-Origin" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limiting_middleware(self, async_client):
        # This would test rate limiting - simplified version
        for _ in range(5):
            response = await async_client.get("/health")
            assert response.status_code == 200

        # After many requests, should get rate limited (if configured)
        # This depends on your rate limiting implementation
```

## Mocking External Services

```python
# app/tests/test_external_services.py
import pytest
from unittest.mock import AsyncMock, patch
import httpx

class TestExternalServices:

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_external_api_call(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from app.services.external_service import fetch_external_data
        result = await fetch_external_data("https://api.example.com/data")

        assert result == {"data": "test"}
        mock_get.assert_called_once()
```

## Performance Testing

```python
# app/tests/test_performance.py
import pytest
import time
import asyncio

class TestPerformance:

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client):
        """Test handling multiple concurrent requests"""
        async def make_request():
            response = await async_client.get("/health")
            return response.status_code

        # Make 10 concurrent requests
        start_time = time.time()
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All requests should succeed
        assert all(status == 200 for status in results)

        # Should complete within reasonable time
        assert (end_time - start_time) < 5.0

    @pytest.mark.asyncio
    async def test_response_time(self, async_client):
        """Test API response time"""
        start_time = time.time()
        response = await async_client.get("/health")
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second
```

## Running Tests

### Command Line

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest app/tests/test_auth.py

# Run specific test
pytest app/tests/test_auth.py::TestAuthentication::test_user_registration

# Run with verbose output
pytest -v

# Run async tests only
pytest -k "asyncio"

# Generate HTML coverage report
pytest --cov=app --cov-report=html
```

### Test Configuration (pytest.ini)

```ini
[tool:pytest]
testpaths = app/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
addopts =
    --strict-markers
    --disable-warnings
    --cov=app
    --cov-report=term-missing
    --cov-fail-under=80
```

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Testing Best Practices

1. **Test Structure**: Follow AAA pattern (Arrange, Act, Assert)
2. **Test Isolation**: Each test should be independent
3. **Mock External Dependencies**: Use mocks for external services
4. **Test Edge Cases**: Include boundary conditions and error cases
5. **Async Testing**: Use pytest-asyncio for async functions
6. **Coverage Goals**: Aim for >80% code coverage
7. **Performance Tests**: Include basic performance testing
8. **Integration Tests**: Test complete workflows
9. **Clear Test Names**: Use descriptive test function names
10. **Documentation**: Comment complex test scenarios
