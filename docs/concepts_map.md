# FastAPI Concepts Implementation Map

**File Location: `docs/concepts_map.md`**

This document maps FastAPI concepts to their implementation in this project.

## Core FastAPI Features

### 1. Application Structure

- **Concept**: FastAPI app instance and routing
- **Implementation**: `app/main.py` - Main app with router includes
- **Files**: `app/api/v1/*.py` - Individual route modules

### 2. Dependency Injection

- **Concept**: FastAPI Depends() system
- **Implementation**: `app/core/dependencies.py`
- **Usage**: Database sessions, authentication, pagination

### 3. Request/Response Models

- **Concept**: Pydantic models for validation
- **Implementation**: `app/schemas/*.py`
- **Features**: Automatic validation, serialization, OpenAPI docs

### 4. Path Operations

- **Concept**: HTTP methods with decorators
- **Implementation**: All `app/api/v1/*.py` files
- **Methods**: GET, POST, PUT, DELETE, PATCH

### 5. Authentication & Security

- **Concept**: OAuth2, JWT tokens, security schemes
- **Implementation**:
  - `app/core/security.py` - JWT handling
  - `app/api/v1/auth.py` - Auth endpoints
  - `app/services/auth_service.py` - Business logic

### 6. Database Integration

- **Concept**: SQLAlchemy ORM integration
- **Implementation**:
  - `app/models/*.py` - ORM models
  - `app/core/dependencies.py` - DB session management

### 7. Background Tasks

- **Concept**: FastAPI BackgroundTasks
- **Implementation**: `app/services/notification_service.py`
- **Use Cases**: Email sending, cleanup tasks

### 8. WebSockets

- **Concept**: Real-time bidirectional communication
- **Implementation**: `app/api/v1/websocket.py`
- **Features**: Connection management, broadcasting

### 9. Server-Sent Events (SSE)

- **Concept**: Real-time server-to-client streaming
- **Implementation**: `app/api/v1/sse.py`
- **Use Cases**: Live updates, progress tracking

### 10. File Uploads/Downloads

- **Concept**: File handling with FastAPI
- **Implementation**: `app/api/v1/uploads.py`
- **Features**: Streaming, validation, storage

### 11. Middleware

- **Concept**: Request/response processing pipeline
- **Implementation**: `app/middleware/*.py`
- **Types**: CORS, rate limiting, request timing

### 12. Exception Handling

- **Concept**: Custom exception handlers
- **Implementation**: `app/exceptions/*.py`
- **Features**: Structured error responses, HTTP status codes

### 13. Configuration Management

- **Concept**: Pydantic Settings
- **Implementation**: `app/core/config.py`
- **Features**: Environment variables, validation

### 14. Testing

- **Concept**: FastAPI TestClient
- **Implementation**: `app/tests/*.py`
- **Features**: Pytest fixtures, async testing

### 15. API Versioning

- **Concept**: URL path versioning
- **Implementation**: `app/api/v1/` and `app/api/v2/`
- **Strategy**: Path-based versioning

## Advanced Features

### Async/Await Patterns

- **Files**: Throughout the codebase
- **Best Practices**: See `docs/async_best_practices.md`

### Caching

- **Implementation**: `app/common/cache_utils.py`
- **Strategy**: Redis-based caching

### API Documentation

- **Concept**: Automatic OpenAPI/Swagger docs
- **Customization**: `app/templates/api_docs.html`
- **Generation**: `scripts/generate_openapi_spec.py`

### Form Data Handling

- **Implementation**: `app/api/v1/forms.py`
- **Features**: Multipart forms, file uploads

## Learning Path

1. Start with `app/main.py` - Application entry point
2. Explore `app/api/v1/users.py` - Basic CRUD operations
3. Study `app/core/dependencies.py` - Dependency injection
4. Review `app/schemas/user.py` - Pydantic models
5. Examine `app/services/auth_service.py` - Business logic
6. Test with `app/tests/test_auth.py` - Testing patterns

## Quick Reference

| Feature  | File               | Key Concepts              |
| -------- | ------------------ | ------------------------- |
| Routes   | `api/v1/*.py`      | @app.get, @app.post       |
| Models   | `schemas/*.py`     | BaseModel, Field          |
| Database | `models/*.py`      | SQLAlchemy ORM            |
| Auth     | `core/security.py` | JWT, OAuth2PasswordBearer |
| Config   | `core/config.py`   | Settings, env vars        |
| Tests    | `tests/*.py`       | TestClient, fixtures      |
