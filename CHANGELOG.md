# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Liveness (`/health/live`) and readiness (`/health/ready`) probes; readiness
  checks PostgreSQL and Redis with timeouts and returns 503 when degraded.
- Prometheus `/metrics` endpoint with request counter, latency histogram,
  in-flight gauge and exception counter, labelled by route template.
- Structured logging (structlog) with per-request correlation ids that are
  propagated from and returned in `X-Request-ID`.
- Sliding-window rate limiting on Redis sorted sets (atomic, burst/minute/hour
  windows, fails open when Redis is down).
- Security headers middleware (nosniff, frame denial, referrer policy, CSP,
  HSTS in production) and gzip compression.
- A/B experiments for courses (`CourseExperiment` model, two-proportion z-test
  results), monthly enrollment cohorts, market-trend analytics, owner-scoped
  bulk course updates, learning paths derived from the catalogue.
- Form submissions listing/detail, multipart and dynamic forms, active surveys
  with response counts, dry-run form validation.
- Alembic: `alembic.ini`, initial migration, and tests asserting the migration
  chain matches the models and downgrades cleanly.
- Tooling: ruff, mypy (zero errors, blocking in CI), pre-commit, GitHub Actions
  (lint / typecheck / tests on 3.11 & 3.12 / Docker build / OpenAPI artefact),
  Dependabot, Makefile.
- Docker: multi-stage image built with uv, non-root user, tini, readiness
  healthcheck, migrations-on-start entrypoint; compose profiles for
  monitoring (Prometheus + Grafana), admin tools and nginx.

### Changed
- SQLAlchemy models rewritten in the 2.0 typed `Mapped[]` style with shared
  timestamp/soft-delete mixins, a naming convention for constraints, and enum
  columns that store their values.
- All timestamps are timezone-aware UTC (`app.core.time.utcnow`, `UTCDateTime`
  column type). `datetime.utcnow()` is gone.
- Settings validated at startup: `ENVIRONMENT` is a literal, secrets are
  `SecretStr`, production refuses placeholder secrets, `DEBUG=true` or
  wildcard CORS.
- Every error response uses one envelope: `{"error", "message", "details",
  "request_id"}`, including validation errors and unhandled exceptions.
- Password hashing uses `bcrypt` directly instead of the unmaintained passlib.
- Request context, security headers, metrics and rate limiting are pure ASGI
  middleware (no `BaseHTTPMiddleware`), so SSE streaming works unbuffered.
- `/docs` and `/redoc` are available in every environment except production.
- Tests use `httpx.ASGITransport`, fakeredis (real Redis semantics) and a
  per-test timeout.

### Fixed
- The application did not import: a truncated exception module, unfinished
  Pydantic v2 migration, missing dependencies (`itsdangerous`, `greenlet`),
  an ambiguous `RefreshToken.user` relationship.
- JWT expiry compared UTC to local time; every token was rejected on machines
  west of UTC.
- Upload router called `FileService` methods that did not exist; public files
  now download without credentials; `delete_file()` signature mismatch.
- Forgot/reset password accept JSON bodies; a bad reset token is a 400, not 401.
- `ExternalServiceException` referenced another class's arguments; `smtplib`
  was never imported in the email service.
- Enrollment response read a non-existent `created_at` attribute.
- nginx proxied WebSockets on the wrong path.

### Removed
- `generate_fastapi_project.sh` (emitted an outdated copy of the code base).
- Placeholder adaptive/endpoint rate limiters that returned fake CPU metrics.
- The non-atomic GET/INCR `RateLimitCache`.
