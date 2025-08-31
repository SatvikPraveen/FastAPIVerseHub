.
├── .env.example
├── .gitignore
├── app
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   ├── v1
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── courses.py
│   │   │   ├── forms.py
│   │   │   ├── sse.py
│   │   │   ├── uploads.py
│   │   │   ├── users.py
│   │   │   └── websocket.py
│   │   └── v2
│   │       ├── __init__.py
│   │       ├── advanced_auth.py
│   │       └── advanced_courses.py
│   ├── common
│   │   ├── __init__.py
│   │   ├── cache_utils.py
│   │   ├── email_utils.py
│   │   ├── file_utils.py
│   │   └── validators.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── exceptions
│   │   ├── __init__.py
│   │   ├── auth_exceptions.py
│   │   ├── base_exceptions.py
│   │   └── validation_exceptions.py
│   ├── main.py
│   ├── middleware
│   │   ├── __init__.py
│   │   ├── cors_middleware.py
│   │   ├── rate_limiter.py
│   │   └── request_timer.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── course.py
│   │   ├── token.py
│   │   └── user.py
│   ├── schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── common.py
│   │   ├── course.py
│   │   └── user.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── course_service.py
│   │   ├── notification_service.py
│   │   └── user_service.py
│   ├── templates
│   │   ├── api_docs.html
│   │   ├── reset_password.html
│   │   └── welcome_email.html
│   └── tests
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_courses.py
│       ├── test_middleware.py
│       ├── test_sse.py
│       ├── test_uploads.py
│       └── test_websockets.py
├── docker-compose.yml
├── Dockerfile
├── docs
│   ├── api_usage_guide.md
│   ├── architecture_decisions.md
│   ├── async_best_practices.md
│   ├── concepts_map.md
│   ├── deployment_guide.md
│   ├── learning_path.md
│   ├── quick_reference.md
│   └── testing_guide.md
├── generate_fastapi_project.sh
├── PROJECT_STRUCTURE.md
├── pyproject.toml
├── README.md
├── scripts
│   ├── benchmark_apis.py
│   ├── generate_fake_data.py
│   ├── generate_openapi_spec.py
│   └── run_tests.sh
└── uploads

17 directories, 77 files
