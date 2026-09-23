# FastAPIVerseHub 🚀

A production-grade FastAPI code base that doubles as a learning resource: typed
SQLAlchemy 2.0 models, tested migrations, structured logging with request
correlation, Prometheus metrics, atomic Redis rate limiting, real-time
WebSockets/SSE, and a CI pipeline that keeps lint, types and tests green.

[![CI](https://github.com/SatvikPraveen/FastAPIVerseHub/actions/workflows/ci.yml/badge.svg)](https://github.com/SatvikPraveen/FastAPIVerseHub/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](https://mypy-lang.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#️-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [API Documentation](#-api-documentation)
- [API Endpoints](#-api-endpoints)
- [Real-time Features](#-real-time-features)
- [Testing](#-testing)
- [Development](#-development)
- [Architecture](#️-architecture)
- [Deployment](#-deployment)
- [Performance](#-performance)
- [Security](#-security)
- [Monitoring](#-monitoring)
- [Learning Resources](#-learning-resources)
- [Contributing](#-contributing)
- [Troubleshooting](#-troubleshooting)
- [Changelog](CHANGELOG.md)
- [License](#-license)

## 🚀 Features

### API & Domain

- ✅ **REST API, versioned** - `/api/v1` core, `/api/v2` advanced auth (MFA, magic links, sessions) and analytics
- ✅ **Typed models** - SQLAlchemy 2.0 `Mapped[]` declarations, shared mixins, named constraints
- ✅ **Tested migrations** - Alembic chain is applied and diffed against the models in CI
- ✅ **One error envelope** - `{"error", "message", "details", "request_id"}` for every failure
- ✅ **UTC everywhere** - timezone-aware timestamps via a custom column type; no naive datetimes
- ✅ **Real-time** - WebSocket rooms/channels and Server-Sent Events (unbuffered, pure-ASGI stack)
- ✅ **Files & forms** - streaming uploads with validation, multipart forms, surveys
- ✅ **Analytics** - enrollment cohorts, market trends, instructor dashboard, A/B experiments with a z-test

### Operations

- 🩺 **Probes** - `/health/live` and `/health/ready` (DB + Redis with timeouts, 503 when degraded)
- 📈 **Metrics** - Prometheus `/metrics` labelled by route template; compose profile with Grafana
- 🧾 **Structured logs** - structlog, JSON in production, `X-Request-ID` propagated end to end
- 🚦 **Rate limiting** - sliding windows on Redis sorted sets, atomic, fails open on outage
- 🔒 **Hardened defaults** - secrets as `SecretStr`, production refuses placeholder config, security headers, bcrypt
- 🐳 **Docker** - multi-stage image (uv), non-root, tini, migrations on start, health-gated compose

### Engineering

- 🧪 **145+ tests** on in-memory SQLite + fakeredis; no external services needed
- 🧹 **ruff + mypy** - zero lint findings, zero type errors, both blocking in CI
- ⚙️ **GitHub Actions** - lint, typecheck, test matrix (3.11/3.12), Docker build, OpenAPI artefact
- 🤖 **Dependabot**, pre-commit hooks, Makefile

## 🛠️ Tech Stack

| Category             | Technology              | Purpose                                   |
| -------------------- | ----------------------- | ----------------------------------------- |
| **Framework**        | FastAPI / Starlette     | ASGI web framework                        |
| **Language**         | Python 3.11+            | `X | None` unions, `StrEnum`, `datetime.UTC` |
| **Validation**       | Pydantic v2             | Schemas and settings                      |
| **Database**         | PostgreSQL 16           | Primary store (SQLite for tests)          |
| **ORM / Migrations** | SQLAlchemy 2.0 / Alembic| Typed async ORM, versioned schema         |
| **Cache & limits**   | Redis 7                 | Caching, rate limiting, token blacklist   |
| **Auth**             | python-jose, bcrypt, pyotp | JWT, password hashing, TOTP MFA        |
| **Observability**    | structlog, prometheus-client | Logs and metrics                     |
| **Testing**          | pytest, httpx, fakeredis| Async tests without external services     |
| **Quality**          | ruff, mypy, pre-commit  | Lint, format, types                       |
| **Packaging**        | uv                      | Fast, reproducible installs               |
| **Runtime**          | Uvicorn, Docker, nginx  | Serving and deployment                    |

## 📁 Project Structure

```
FastAPIVerseHub/
├── app/
│   ├── main.py                 # app factory, lifespan, middleware stack, error envelope
│   ├── api/
│   │   ├── health.py           # /health, /health/live, /health/ready
│   │   ├── v1/                 # auth, users, courses, uploads, forms, websocket, sse
│   │   └── v2/                 # advanced auth (MFA, magic link, sessions), advanced courses
│   ├── core/
│   │   ├── config.py           # validated Settings (SecretStr, production guards)
│   │   ├── dependencies.py     # DB session, Redis, current-user dependencies
│   │   ├── logging.py          # structlog + request correlation
│   │   ├── metrics.py          # Prometheus middleware + /metrics
│   │   ├── security.py         # bcrypt hasher, JWT manager
│   │   └── time.py             # utcnow(), aware-datetime helpers
│   ├── middleware/             # pure-ASGI: request context, rate limit, security headers, CORS
│   ├── models/                 # SQLAlchemy 2.0 typed models, mixins, UTCDateTime
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # business logic (auth, users, courses, files, forms, analytics…)
│   ├── common/                 # cache manager, sliding-window limiter, file/email utils
│   ├── exceptions/             # application exception hierarchy
│   ├── templates/              # Jinja2 email templates
│   └── tests/                  # pytest suite (SQLite + fakeredis, migration drift tests)
├── alembic/                    # migration environment and versions/
├── docker/                     # entrypoint, Prometheus + Grafana provisioning
├── docs/                       # guides and ADRs
├── nginx/                      # reverse proxy config (TLS, WS, SSE, /metrics allow-list)
├── scripts/                    # fake data, benchmarks, OpenAPI export, test runner
├── .github/workflows/ci.yml    # lint · typecheck · tests · docker · openapi
├── docker-compose.yml          # app + postgres + redis (+ monitoring / admin / nginx profiles)
├── Dockerfile                  # multi-stage, uv, non-root, tini
├── Makefile                    # make install | lint | typecheck | test | run | migrate
└── pyproject.toml              # deps, ruff, mypy, pytest, coverage config
```

## 🚦 Quick Start

### Prerequisites

- 🐍 **Python 3.11+** and [**uv**](https://docs.astral.sh/uv/) (`pip install uv` works too)
- 🐳 **Docker** (optional, for the full stack)

### Option 1: Docker (🔥 recommended)

```bash
git clone https://github.com/SatvikPraveen/FastAPIVerseHub.git
cd FastAPIVerseHub
docker compose up -d --build          # api + postgres + redis; migrations run on start

curl -s localhost:8000/health/ready | jq   # {"status": "ready", ...}
open http://localhost:8000/docs

# optional profiles
docker compose --profile monitoring up -d  # Prometheus :9090, Grafana :3001
docker compose --profile admin up -d       # pgAdmin :5050, Redis Commander :8081
```

### Option 2: Local development

```bash
git clone https://github.com/SatvikPraveen/FastAPIVerseHub.git
cd FastAPIVerseHub
make install                          # uv venv + deps + pre-commit hooks
cp .env.example .env                  # point DATABASE_* / REDIS_* at your services

make migrate                          # alembic upgrade head
make run                              # uvicorn with reload on :8000
```

### Verify

```bash
make lint typecheck test              # ruff · mypy · pytest (no services required)
```

## 📚 API Documentation

Once running, access the comprehensive API documentation:

| Documentation Type  | URL                                | Description                    |
| ------------------- | ---------------------------------- | ------------------------------ |
| **🎨 Swagger UI**   | http://localhost:8000/docs         | Interactive API documentation  |
| **📖 ReDoc**        | http://localhost:8000/redoc        | Alternative documentation view |
| **📋 OpenAPI Spec** | http://localhost:8000/openapi.json | Raw OpenAPI specification      |

Docs are served in every environment except `production`. Export the spec with
`python scripts/generate_openapi_spec.py` (JSON, YAML, Markdown and a Postman
collection under `docs/openapi/`; CI publishes the same as an artefact).

### 🔑 Seed data

```bash
python scripts/generate_fake_data.py     # users (password: password123), courses, enrollments
```

## 🌐 API Endpoints

Every error response has the same shape, so clients can switch on `error`:

```json
{"error": "VALIDATION_ERROR", "message": "Request validation failed",
 "details": {"errors": [{"field": "email", "message": "value is not a valid email address"}]},
 "request_id": "3f1c9b2e0d0d4b6f9a1c2d3e4f5a6b7c"}
```

### 🔑 Authentication (`/api/v1/auth`, `/api/v2/auth`)

| Method | Endpoint                          | Description                          | Auth |
| ------ | --------------------------------- | ------------------------------------ | ---- |
| `POST` | `/api/v1/auth/register`           | Register, returns token pair         | ❌   |
| `POST` | `/api/v1/auth/login`              | Login                                | ❌   |
| `POST` | `/api/v1/auth/refresh`            | Rotate access token                  | ❌   |
| `POST` | `/api/v1/auth/logout`             | Revoke token (jti blacklist)         | ✅   |
| `POST` | `/api/v1/auth/forgot-password`    | Request reset token                  | ❌   |
| `POST` | `/api/v1/auth/reset-password`     | Reset with token                     | ❌   |
| `POST` | `/api/v2/auth/mfa/setup` `/verify` `/disable` | TOTP MFA lifecycle       | ✅   |
| `POST` | `/api/v2/auth/passwordless/request` `/verify` | Magic-link login         | ❌   |
| `GET`  | `/api/v2/auth/sessions`           | List / revoke sessions               | ✅   |

### 👥 Users & 📚 Courses

| Method              | Endpoint                          | Description                        | Auth |
| ------------------- | --------------------------------- | ---------------------------------- | ---- |
| `GET/PUT/DELETE`    | `/api/v1/users/me`                | Own profile                        | ✅   |
| `GET`               | `/api/v1/users/`                  | List users (admin)                 | 👑   |
| `GET`               | `/api/v1/courses/`                | List/search courses                | ❌   |
| `POST`              | `/api/v1/courses/`                | Create course                      | ✅   |
| `GET/PUT/DELETE`    | `/api/v1/courses/{course_id}`     | Course detail / update / delete    | ❌/✅ |
| `POST/DELETE`       | `/api/v1/courses/{course_id}/enroll` | Enroll / unenroll               | ✅   |
| `GET`               | `/api/v2/courses/recommendations` | Recommendations                    | ✅   |
| `GET`               | `/api/v2/courses/analytics/{id}`  | Course analytics (owner)           | ✅   |
| `GET`               | `/api/v2/courses/cohorts/{id}`    | Monthly enrollment cohorts         | ✅   |
| `POST`              | `/api/v2/courses/experiments/ab-test` | Create A/B experiment          | ✅   |
| `GET`               | `/api/v2/courses/trends/market`   | Demand / pricing signals           | ❌   |

### 📁 Files & 📝 Forms

| Method   | Endpoint                             | Description                     | Auth |
| -------- | ------------------------------------ | ------------------------------- | ---- |
| `POST`   | `/api/v1/uploads/file` `/multiple`   | Upload (streamed, hashed)       | ✅   |
| `GET`    | `/api/v1/uploads/download/{file_id}` | Download (public files: no auth)| ❌/✅ |
| `GET`    | `/api/v1/uploads/stream/{file_id}`   | Chunked stream                  | ✅   |
| `GET`    | `/api/v1/uploads/categories` `/stats`| Per-user aggregates             | ✅   |
| `POST`   | `/api/v1/forms/contact` `/feedback` `/survey` `/multipart` `/dynamic` | Submissions | varies |
| `POST`   | `/api/v1/forms/validate`             | Dry-run validation              | ❌   |

### 📊 System

| Method | Endpoint        | Description                                   | Auth |
| ------ | --------------- | --------------------------------------------- | ---- |
| `GET`  | `/health/live`  | Liveness                                      | ❌   |
| `GET`  | `/health/ready` | Readiness (DB + Redis), 503 when degraded     | ❌   |
| `GET`  | `/metrics`      | Prometheus exposition                         | ❌ (restrict at the proxy) |

Rate-limited responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
`X-RateLimit-Reset` and, on 429, `Retry-After`. Every response carries
`X-Request-ID` and `X-Process-Time`.

## 🔄 Real-time Features

### 🌐 WebSocket

```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/ws/connect/my-client?token=" + jwt);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onopen = () => {
  ws.send(JSON.stringify({ type: "subscribe", channel: "general" }));
  ws.send(JSON.stringify({ type: "broadcast", channel: "general", content: "Hello!" }));
};
```

Message types: `ping`, `subscribe`, `unsubscribe`, `broadcast`, `private_message`,
`join_room`, `leave_room`, `room_message`. Stats at `GET /api/v1/ws/stats`.

### 📡 Server-Sent Events

```javascript
const es = new EventSource("http://localhost:8000/api/v1/sse/events?channels=general,updates");
es.addEventListener("connected", (e) => console.log("connected", JSON.parse(e.data)));
es.addEventListener("message", (e) => console.log(JSON.parse(e.data)));
```

Publish with `POST /api/v1/sse/publish/{channel}` or `POST /api/v1/sse/broadcast`.
The stream ends as soon as the client disconnects; the middleware stack is pure
ASGI so events are not buffered.

## 🧪 Testing

```bash
make test         # full suite with coverage (fails under 80%)
make test-fast    # parallel, no coverage
pytest app/tests/test_rate_limit.py -k concurrent -v
```

- Runs entirely in-process: async SQLite in memory and **fakeredis** with real
  Redis command semantics. No Docker, no services.
- `test_migrations.py` applies the Alembic chain to a scratch database and
  asserts zero drift against the models, then downgrades to empty.
- Every test has a 60 s timeout, so a stalled stream fails fast.
- Load test a running instance: `python scripts/benchmark_apis.py --total 200 --concurrent 20`.

See [`docs/testing_guide.md`](docs/testing_guide.md).

## 🔧 Development

```bash
make help          # list targets
make lint          # ruff check
make format        # ruff --fix + ruff format
make typecheck     # mypy app  (zero errors is the bar)
make migrate       # alembic upgrade head
alembic revision --autogenerate -m "add thing"   # then run make test: drift is asserted
```

`pre-commit install` (done by `make install`) runs ruff, ruff-format and mypy
on every commit. CI runs the same checks plus the test matrix and a Docker build.

### 🐳 Docker development

```bash
docker compose up -d --build
docker compose logs -f app
docker compose exec app alembic history
docker compose exec db psql -U fastapi_user -d fastapi_verse_hub
docker compose --profile monitoring up -d    # Prometheus + Grafana
```

The image runs migrations on start (`SKIP_MIGRATIONS=1` to disable), serves with
`WEB_CONCURRENCY` uvicorn workers behind tini, and reports readiness via the
container healthcheck.

## 🏗️ Architecture

### 🎯 Project Philosophy

- **🏛️ Clean Architecture** - Clear separation of concerns
- **🎯 Domain-Driven Design** - Business logic in services layer
- **⚡ SOLID Principles** - Maintainable and extensible code
- **🧪 Test-Driven Development** - Comprehensive test coverage
- **📋 API-First Design** - OpenAPI specification driven

### 🧩 Key Components

#### ⚙️ Core Layer (`app/core/`)

- **🔧 Configuration Management** - Pydantic Settings with environment variables
- **🔐 Security Utilities** - JWT handling and password hashing
- **🗃️ Database Connection** - Async SQLAlchemy setup
- **💉 Dependency Injection** - FastAPI dependencies
- **📝 Structured Logging** - JSON logging with correlation IDs

#### 🌐 API Layer (`app/api/`)

- **🛣️ RESTful Endpoints** - Standard HTTP methods and status codes
- **✅ Request/Response Validation** - Automatic Pydantic validation
- **❌ Error Handling** - Consistent error responses
- **📌 API Versioning** - Support for multiple API versions

#### 🏢 Business Logic (`app/services/`)

- **📈 Domain Rules** - Business logic implementation
- **🗃️ Database Operations** - Data access patterns
- **🌐 External Integrations** - Third-party service calls
- **⚡ Background Tasks** - Async task management

#### 🗃️ Data Layer (`app/models/`)

- **📊 ORM Models** - SQLAlchemy database models
- **🔗 Relationships** - Database table relationships
- **✅ Constraints** - Data integrity rules

#### 📋 Validation Layer (`app/schemas/`)

- **📥 Request Models** - Input validation schemas
- **📤 Response Models** - Output serialization schemas
- **📚 Documentation** - Automatic API docs generation

## 🚀 Deployment

### 🐳 Docker Production

```bash
# Build the runtime image (multi-stage, non-root, tini, migrations on start)
docker build -t fastapiversehub:latest .

# Run behind the bundled nginx (TLS, WebSocket/SSE proxying, /metrics allow-list)
docker compose --profile production up -d

# Required production environment (startup refuses unsafe values):
#   ENVIRONMENT=production  JWT_SECRET_KEY=<openssl rand -hex 32>
#   DATABASE_URL=postgresql://...  REDIS_URL=redis://...  CORS_ORIGINS=https://app.example.com
docker compose ps && docker compose logs -f app
```

### 🖥️ Traditional Server

```bash
# 📦 Install production dependencies
pip install -e ".[production]"

# 🚀 Run with Gunicorn
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

### ☁️ Cloud Deployment

The project includes deployment configurations for:

| Platform            | Service             | Configuration                 |
| ------------------- | ------------------- | ----------------------------- |
| **🟠 AWS**          | ECS/Fargate         | Container-based deployment    |
| **🔵 Google Cloud** | Cloud Run           | Serverless container platform |
| **🟦 Azure**        | Container Instances | Simple container deployment   |
| **☸️ Kubernetes**   | Any cluster         | Full orchestration setup      |

📚 **Detailed Instructions**: See [`docs/deployment_guide.md`](docs/deployment_guide.md)

## 📈 Performance

### 🎯 Performance Benchmarks

| Metric                  | Target    | Description                      |
| ----------------------- | --------- | -------------------------------- |
| **⚡ Response Time**    | < 50ms    | Average for simple endpoints     |
| **🚀 Throughput**       | 1000+ RPS | Requests per second with caching |
| **👥 Concurrent Users** | 500+      | WebSocket connections            |
| **📁 File Upload**      | 100MB+    | Streaming support                |

### 🔧 Optimization Features

- **💾 Redis Caching** - Database query caching
- **🏊 Connection Pooling** - Efficient database connections
- **⚡ Async/Await** - Non-blocking operations throughout
- **⚙️ Background Tasks** - Offloaded processing
- **🗜️ Response Compression** - Reduced payload sizes

### 📊 Performance Monitoring

```bash
# 🔍 Run performance benchmarks
python scripts/benchmark_apis.py \
    --concurrent 10 \
    --total 1000 \
    --export performance_report.json

# 📈 Analyze results
# Check average response times, error rates, and throughput
```

## 🔒 Security

### 🛡️ Implemented Security Measures

| Feature                  | Implementation    | Description                  |
| ------------------------ | ----------------- | ---------------------------- |
| **🔑 Authentication**    | JWT tokens        | Stateless authentication     |
| **🔒 Password Security** | bcrypt hashing    | Secure password storage      |
| **🌐 CORS Protection**   | Starlette CORS    | Explicit origins; wildcard refused in production |
| **🚦 Rate Limiting**     | Sliding window (Redis ZSET) | Atomic, burst/minute/hour, fails open |
| **✅ Input Validation**  | Pydantic models   | Data sanitization            |
| **🛡️ SQL Injection**     | SQLAlchemy ORM    | Parameterized queries        |
| **📁 File Security**     | Type validation   | Safe file uploads            |
| **🔐 Security Headers**  | Pure-ASGI middleware | nosniff, DENY framing, CSP, HSTS in prod |
| **⚙️ Config guards**     | Settings validator | Placeholder secrets / DEBUG rejected in production |

### 🔐 Security Best Practices

```bash
# 🔑 Generate secure keys for production
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 🔍 Security audit
uv pip install pip-audit bandit
pip-audit
bandit -r app/ -c pyproject.toml
```

## 📊 Monitoring

| Endpoint        | Purpose                                        |
| --------------- | ---------------------------------------------- |
| `/health/live`  | Process up; never touches dependencies         |
| `/health/ready` | DB + Redis checked with timeouts; 503 if not   |
| `/metrics`      | Prometheus: requests, latency histogram, in-flight, exceptions (by route template) |

Logs are structured (structlog); `LOG_FORMAT=json` in production. Every line and
every error body carries the `request_id`, which is also returned as
`X-Request-ID` and accepted from upstream proxies.

```bash
curl -s localhost:8000/metrics | grep http_request_duration_seconds_bucket | head
docker compose --profile monitoring up -d && open http://localhost:3001
```

## 📖 Learning Resources

### 🎓 Recommended Learning Path

| Step | Resource                                                           | Duration  | Focus                    |
| ---- | ------------------------------------------------------------------ | --------- | ------------------------ |
| 1️⃣   | [`docs/learning_path.md`](docs/learning_path.md)                   | 2-3 weeks | Complete FastAPI journey |
| 2️⃣   | [`docs/quick_reference.md`](docs/quick_reference.md)               | 1 day     | FastAPI patterns         |
| 3️⃣   | [`docs/api_usage_guide.md`](docs/api_usage_guide.md)               | 2 days    | API usage examples       |
| 4️⃣   | [`docs/architecture_decisions.md`](docs/architecture_decisions.md) | 1 day     | Design decisions         |
| 5️⃣   | [`docs/testing_guide.md`](docs/testing_guide.md)                   | 3 days    | Testing strategies       |
| 6️⃣   | [`docs/deployment_guide.md`](docs/deployment_guide.md)             | 2 days    | Production deployment    |

### 💡 Key Concepts Demonstrated

- **⚡ Async Programming** - Proper async/await usage patterns
- **💉 Dependency Injection** - FastAPI's powerful DI system
- **✅ Data Validation** - Pydantic models and custom validators
- **🔑 Authentication** - JWT and OAuth2 implementation
- **🔄 Real-time Communication** - WebSockets and Server-Sent Events
- **🧪 Testing** - Comprehensive testing strategies
- **📋 API Design** - RESTful best practices and standards

### 📚 External Resources

- 📖 [FastAPI Official Documentation](https://fastapi.tiangolo.com/)
- 📖 [Pydantic Documentation](https://docs.pydantic.dev/)
- 📖 [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- 📖 [pytest Documentation](https://docs.pytest.org/)
- 📖 [Docker Documentation](https://docs.docker.com/)

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### 🚀 Quick Contribution Guide

1. **🍴 Fork** the repository
2. **🌿 Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **💻 Make** your changes with tests
4. **🧪 Ensure** `make lint typecheck test` passes
5. **📝 Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **⬆️ Push** to branch (`git push origin feature/amazing-feature`)
7. **🔄 Open** a Pull Request

### 📋 Development Guidelines

- **🎨 Code Style** - `ruff format` + `ruff check` (configured in `pyproject.toml`)
- **🔤 Type Hints** - Add type hints to all functions
- **🧪 Testing** - Write tests for new functionality (aim for 90%+ coverage)
- **📚 Documentation** - Update relevant documentation
- **⚡ Commits** - Keep commits atomic and well-described

### 🏷️ Contribution Types

- 🐛 **Bug Fixes** - Fix issues and improve stability
- ✨ **New Features** - Add new functionality
- 📚 **Documentation** - Improve docs and examples
- 🎨 **Code Quality** - Refactoring and optimization
- 🧪 **Testing** - Add or improve tests
- 🔒 **Security** - Security improvements

### 🎯 Good First Issues

Look for issues labeled with:

- `good-first-issue` - Perfect for beginners
- `documentation` - Documentation improvements
- `tests` - Adding or improving tests
- `enhancement` - Small feature additions

## 🐛 Troubleshooting

### 🔍 Common Issues

<details>
<summary><strong>🗃️ Database Connection Errors</strong></summary>

```bash
# Check if database is running
docker compose ps db

# Check connection string
echo $DATABASE_URL

# Reset database
docker compose down -v
docker compose up -d db

# Check logs
docker compose logs db
```

</details>

<details>
<summary><strong>💾 Redis Connection Issues</strong></summary>

```bash
# Test Redis connectivity
redis-cli ping  # Should return PONG

# Check Redis URL
echo $REDIS_URL

# Restart Redis
docker compose restart redis

# Check Redis logs
docker compose logs redis
```

</details>

<details>
<summary><strong>📦 Import Errors</strong></summary>

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -e ".[dev]"

# Check Python path
python -c "import sys; print(sys.path)"

# Ensure __init__.py files exist
find app -name "__init__.py" | head -10
```

</details>

<details>
<summary><strong>🔐 Permission Errors</strong></summary>

```bash
# Fix upload directory permissions
chmod -R 755 uploads/

# Fix Docker volume permissions
sudo chown -R $USER:$USER uploads/

# Check file ownership
ls -la uploads/
```

</details>

<details>
<summary><strong>🚀 Application Won't Start</strong></summary>

```bash
# Check if port is in use
lsof -i :8000

# Check environment variables
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"

# Start with debug mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# Check application logs
docker compose logs -f app
```

</details>

### 🆘 Getting Help

- **📊 GitHub Issues** - [Report bugs or request features](https://github.com/SatvikPraveen/FastAPIVerseHub/issues)
- **💬 Discussions** - [Ask questions and share ideas](https://github.com/SatvikPraveen/FastAPIVerseHub/discussions)
- **📧 Email** - Contact the maintainer for urgent issues

## 🏆 Project Goals

This project serves as a comprehensive learning resource and production-ready template for:

1. **🎓 Learning FastAPI** - From basic concepts to advanced patterns
2. **📈 Best Practices** - Industry-standard development patterns
3. **🏭 Real-world Usage** - Production-ready features and deployment
4. **🌍 Community Education** - Open-source learning resource
5. **🚀 Template for Projects** - Starter template for new FastAPI projects

## 📊 Project Statistics

- **🧪 Tests**: 145+ (unit, integration, migration drift, concurrency)
- **🧹 Lint / types**: ruff clean, mypy 0 errors
- **📋 API Endpoints**: 60+ across v1 and v2
- **📚 Docs**: 8 guides + 17 ADRs, plus a changelog
- **🛠️ Utility Scripts**: 4

## 🎯 Roadmap

### 🔜 Upcoming Features

- **🔐 OAuth2 Social Login** - Google, GitHub, Facebook integration
- **📊 Admin Dashboard** - Web-based administration interface
- **🔍 Full-text Search** - Elasticsearch integration
- **📱 Mobile API** - Mobile-optimized endpoints
- **🌍 Internationalization** - Multi-language support

### 🏗️ Technical Improvements

- **🔭 Tracing** - OpenTelemetry spans exported alongside the existing metrics/logs
- **📨 Task queue** - Move email and report generation to a worker (arq/Celery)
- **🗂️ Object storage** - S3-compatible backend for uploads
- **🗺️ GraphQL** - GraphQL endpoints alongside REST
- **☸️ Helm chart** - Kubernetes-native deployment with the probes already provided

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### 📋 License Summary

```
MIT License - Free for commercial and private use
✅ Commercial use    ✅ Modification    ✅ Distribution    ✅ Private use
❌ Liability         ❌ Warranty
```

## 🙏 Acknowledgments

### 🏆 Special Thanks

- **⚡ [FastAPI](https://fastapi.tiangolo.com/)** - The amazing web framework by Sebastián Ramirez
- **📋 [Pydantic](https://docs.pydantic.dev/)** - Data validation and settings management
- **🗃️ [SQLAlchemy](https://www.sqlalchemy.org/)** - The Python SQL toolkit and ORM
- **⭐ [Starlette](https://www.starlette.io/)** - Lightweight ASGI framework
- **🧪 [pytest](https://docs.pytest.org/)** - Testing framework
- **🌟 **Open Source Community\*\* - For inspiration and contributions

### 👥 Contributors

- **[Satvik Praveen](https://github.com/SatvikPraveen)** - Project creator and maintainer
- **Community Contributors** - Thank you to everyone who contributes!

## 🔗 Links

| Resource             | URL                                                                                | Description                      |
| -------------------- | ---------------------------------------------------------------------------------- | -------------------------------- |
| **📚 Documentation** | [docs/](docs/)                                                                     | Complete project documentation   |
| **🎨 API Reference** | [http://localhost:8000/docs](http://localhost:8000/docs)                           | Interactive API documentation    |
| **🐛 Issues**        | [GitHub Issues](https://github.com/SatvikPraveen/FastAPIVerseHub/issues)           | Bug reports and feature requests |
| **💬 Discussions**   | [GitHub Discussions](https://github.com/SatvikPraveen/FastAPIVerseHub/discussions) | Community discussions            |
| **⭐ Repository**    | [GitHub Repo](https://github.com/SatvikPraveen/FastAPIVerseHub)                    | Source code repository           |
| **👤 Author**        | [@SatvikPraveen](https://github.com/SatvikPraveen)                                 | Project maintainer               |

---

<div align="center">

**🚀 Happy coding! 🚀**

_FastAPIVerseHub - Where FastAPI learning meets real-world application._

**⭐ If you find this project helpful, please give it a star! ⭐**

</div>
