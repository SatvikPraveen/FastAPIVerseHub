# Architecture Decision Records (ADRs)

**File Location: `docs/architecture_decisions.md`**

## Overview

This document explains the architectural decisions made for the FastAPIVerseHub project and the reasoning behind each choice.

## ADR-001: Project Structure Organization

**Decision**: Use a layered architecture with separate directories for API routes, models, schemas, services, and utilities.

**Context**: Need a scalable structure that supports multiple developers and feature growth.

**Rationale**:

- **Separation of Concerns**: Each layer has a specific responsibility
- **Maintainability**: Easy to locate and modify specific functionality
- **Testability**: Clear boundaries make unit testing straightforward
- **Scalability**: Structure supports adding new features without major refactoring

**Consequences**:

- ✅ Clear code organization
- ✅ Easier onboarding for new developers
- ✅ Better separation of business logic from API logic
- ❌ Slightly more boilerplate code

## ADR-002: API Versioning Strategy

**Decision**: Use URL path-based versioning (`/api/v1/`, `/api/v2/`)

**Context**: Need to support API evolution without breaking existing clients.

**Alternatives Considered**:

- Header-based versioning
- Query parameter versioning
- Content-type versioning

**Rationale**:

- **Simplicity**: Easy to understand and implement
- **Visibility**: Version is clear in the URL
- **Caching**: Better support for HTTP caching
- **Documentation**: Easier to document different versions

**Consequences**:

- ✅ Clear version identification
- ✅ Easy to maintain multiple versions
- ❌ URL namespace pollution

## ADR-003: Database ORM Choice

**Decision**: Use SQLAlchemy with Alembic for database operations

**Context**: Need robust database integration with migration support.

**Alternatives Considered**:

- Raw SQL queries
- Other ORMs (Tortoise ORM, Peewee)

**Rationale**:

- **Maturity**: Well-established with extensive documentation
- **FastAPI Integration**: Excellent compatibility with FastAPI
- **Migration Support**: Alembic provides robust schema management
- **Performance**: Good performance with optimization options

**Consequences**:

- ✅ Type safety and validation
- ✅ Database migrations
- ✅ Query optimization
- ❌ Learning curve for complex queries

## ADR-004: Authentication Strategy

**Decision**: JWT tokens with OAuth2 password flow

**Context**: Need secure, stateless authentication for API access.

**Alternatives Considered**:

- Session-based authentication
- API keys
- OAuth2 with external providers

**Rationale**:

- **Stateless**: No server-side session storage required
- **Scalable**: Works well in distributed systems
- **Standard**: OAuth2 is industry standard
- **FastAPI Support**: Built-in support in FastAPI

**Consequences**:

- ✅ Stateless and scalable
- ✅ Industry standard approach
- ✅ Good security when implemented correctly
- ❌ Token management complexity
- ❌ Potential security issues if not handled properly

## ADR-005: Schema Validation

**Decision**: Use Pydantic models for request/response validation

**Context**: Need robust data validation and serialization.

**Rationale**:

- **FastAPI Native**: Pydantic is the default for FastAPI
- **Type Safety**: Python type hints integration
- **Automatic Documentation**: OpenAPI schema generation
- **Performance**: Fast validation with helpful error messages

**Consequences**:

- ✅ Automatic API documentation
- ✅ Type safety and validation
- ✅ Clear data contracts
- ❌ Learning curve for complex validation

## ADR-006: Error Handling Strategy

**Decision**: Custom exception hierarchy with structured error responses

**Context**: Need consistent error handling across the application.

**Implementation**:

- Custom exception classes in `app/exceptions/`
- Structured JSON error responses
- HTTP status code mapping

**Rationale**:

- **Consistency**: Same error format across all endpoints
- **Debugging**: Clear error messages and codes
- **Client Integration**: Predictable error structure for clients

**Consequences**:

- ✅ Consistent error responses
- ✅ Better debugging experience
- ✅ Easier client error handling
- ❌ Additional code for exception mapping

## ADR-007: Business Logic Layer

**Decision**: Separate services layer for business logic

**Context**: Keep API routes thin and business logic reusable.

**Structure**: Services in `app/services/` directory

**Rationale**:

- **Single Responsibility**: API routes handle HTTP concerns only
- **Reusability**: Business logic can be used across different interfaces
- **Testability**: Easier to unit test business logic
- **Maintainability**: Clear separation of concerns

**Consequences**:

- ✅ Cleaner API routes
- ✅ Reusable business logic
- ✅ Better testability
- ❌ Additional abstraction layer

## ADR-008: Real-time Communication

**Decision**: Support both WebSockets and Server-Sent Events

**Context**: Different use cases require different real-time patterns.

**Use Cases**:

- **WebSockets**: Bidirectional communication (chat, collaboration)
- **SSE**: Server-to-client streaming (notifications, live updates)

**Rationale**:

- **Flexibility**: Different tools for different needs
- **Compatibility**: SSE works with standard HTTP
- **Features**: WebSockets for complex interactions

**Consequences**:

- ✅ Covers multiple real-time patterns
- ✅ Good browser compatibility
- ❌ More complexity in infrastructure

## ADR-009: File Handling Strategy

**Decision**: Support streaming uploads/downloads with validation

**Context**: Handle files efficiently without memory issues.

**Features**:

- Streaming for large files
- File type validation
- Size limits
- Secure storage paths

**Rationale**:

- **Performance**: Streaming prevents memory issues
- **Security**: Validation prevents malicious uploads
- **User Experience**: Progress tracking for large files

**Consequences**:

- ✅ Efficient file handling
- ✅ Security validation
- ✅ Good user experience
- ❌ Additional complexity

## ADR-010: Testing Strategy

**Decision**: Comprehensive testing with pytest and FastAPI TestClient

**Context**: Ensure code quality and prevent regressions.

**Approach**:

- Unit tests for services
- Integration tests for API endpoints
- Test fixtures for data setup
- Async testing support

**Rationale**:

- **Quality**: Catch bugs early
- **Confidence**: Safe refactoring
- **Documentation**: Tests serve as usage examples

**Consequences**:

- ✅ Higher code quality
- ✅ Safer deployments
- ✅ Better documentation
- ❌ Additional development time

## ADR-011: Configuration Management

**Decision**: Pydantic Settings with environment variables

**Context**: Need flexible configuration for different environments.

**Features**:

- Environment variable support
- Type validation
- Default values
- Environment-specific configs

**Rationale**:

- **Security**: Secrets in environment variables
- **Flexibility**: Different configs per environment
- **Validation**: Type-safe configuration

**Consequences**:

- ✅ Secure configuration management
- ✅ Environment flexibility
- ✅ Type safety
- ❌ Configuration complexity

## ADR-012: Middleware Strategy

**Decision**: Custom middleware for cross-cutting concerns

**Context**: Handle common functionality across all requests.

**Implementation**:

- Rate limiting
- Request timing
- CORS handling
- Logging

**Rationale**:

- **DRY**: Single implementation for common features
- **Performance**: Efficient request processing
- **Monitoring**: Request timing and logging

**Consequences**:

- ✅ Centralized cross-cutting concerns
- ✅ Better monitoring
- ✅ Consistent behavior
- ❌ Debugging complexity

## ADR-013: Typed ORM Models and UTC-Only Timestamps

**Decision**: Declare every model with SQLAlchemy 2.0 `Mapped[]` annotations on a
`DeclarativeBase`, and store all timestamps through a custom `UTCDateTime`
column type that is always timezone-aware.

**Context**: The legacy `Column()` style gave mypy no information about
attribute types, so services compiled with hundreds of false positives and
real bugs hid among them. Naive `datetime.utcnow()` values compared against
local-time conversions caused a token-expiry bug that rejected every token on
machines west of UTC.

**Rationale**:

- `Mapped[int]` is a real `int` to the type checker; service code is checked
- A `type_annotation_map` means `datetime` fields need no per-column type
- `UTCDateTime` normalises on write and re-tags naive values on read, so
  application code never sees a naive datetime regardless of backend
- Mixins (`TimestampMixin`, `SoftDeleteMixin`) remove copy-pasted columns
- A `MetaData` naming convention gives every constraint a stable name, which
  is what makes Alembic downgrades possible

**Consequences**:

- ✅ mypy runs clean and is a blocking CI check
- ✅ Enum columns persist their *values* (`"beginner"`), matching the API
- ❌ SQLite still stores naive strings; comparisons rely on the type decorator

## ADR-014: One Error Envelope

**Decision**: Every non-2xx response body has the shape
`{"error": CODE, "message": text, "details": {...}, "request_id": id}`,
produced by handlers for `BaseAppException`, `HTTPException`,
`RequestValidationError` and unhandled `Exception`.

**Rationale**: Clients branch on a machine-readable `error` code rather than
parsing prose, validation errors are flattened to `field`/`message` pairs,
and the correlation id in the body lets a user quote it to support.

**Consequences**:

- ✅ Uniform client handling; 500s never leak stack traces
- ❌ FastAPI's default `{"detail": ...}` shape is gone (documented breaking change)

## ADR-015: Sliding-Window Rate Limiting on Redis

**Decision**: Rate limit with a sorted-set sliding window executed as one
Redis transaction per request, with burst (10 s), minute and hour windows.
The middleware fails *open* if Redis is unreachable.

**Alternatives Considered**: fixed-window counters (GET/INCR/EXPIRE), token
bucket in Lua, proxy-only limiting in nginx.

**Rationale**:

- The GET/INCR pair races under concurrency and over-admits; a MULTI/EXEC
  transaction does not
- A sliding window has no boundary burst (2x the limit straddling a reset)
- Rejected requests are removed again so a client cannot lock itself out
- Failing open keeps an outage in the cache tier from becoming an API outage;
  nginx still applies a coarse per-IP limit in front

**Consequences**:

- ✅ Correct under concurrency (covered by a 40-way `asyncio.gather` test)
- ❌ One ZSET per client per window; memory is bounded by `limit` entries each

## ADR-016: Observability Baseline

**Decision**: Ship structured logs with request correlation, Prometheus
metrics labelled by route template, and separate liveness/readiness probes;
implement the request-path pieces as raw ASGI middleware.

**Rationale**:

- `BaseHTTPMiddleware` buffers streaming responses (breaks SSE) and reorders
  background tasks; raw ASGI callables do neither
- Route-template labels keep metric cardinality bounded; raw paths would
  create a new series per id
- Readiness that returns 503 lets a load balancer drain a bad instance
  without the orchestrator restarting a healthy process
- A validated incoming `X-Request-ID` is honoured so traces span the proxy

**Consequences**:

- ✅ One grep on a request id reconstructs a request end to end
- ✅ `docker compose --profile monitoring up` gives Prometheus + Grafana locally
- ❌ Middleware code is more verbose than `dispatch()` style

## ADR-017: Migrations Are Tested

**Decision**: CI applies `alembic upgrade head` to an empty database, asserts
`compare_metadata()` reports no drift against the models, then runs
`downgrade base` and asserts no tables remain.

**Rationale**: A model change without a migration is the most common way a
deploy breaks; catching it in the test suite is cheaper than in production.
Migrations render custom types as plain SQLAlchemy types so they never import
application code and keep working after refactors.
