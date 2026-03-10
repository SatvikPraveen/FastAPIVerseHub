# File: app/models/__init__.py
"""
Import all models here so that Base.metadata is fully populated
before any call to Base.metadata.create_all() or Alembic migrations.
"""

from app.models.base import Base  # noqa: F401 – shared declarative base

# User-side models
from app.models.user import (  # noqa: F401
    User,
    DeviceRegistration,
    UserSession,
    FileUpload,
    FormSubmission,
    Survey,
)

# Course-side models
from app.models.course import (  # noqa: F401
    Course,
    Lesson,
    Enrollment,
    CourseReview,
    UserLessonProgress,
)

# Token models
from app.models.token import (  # noqa: F401
    Token,
    RefreshToken,
    APIKey,
    APIKeyUsageLog,
)

__all__ = [
    "Base",
    "User",
    "DeviceRegistration",
    "UserSession",
    "FileUpload",
    "FormSubmission",
    "Survey",
    "Course",
    "Lesson",
    "Enrollment",
    "CourseReview",
    "UserLessonProgress",
    "Token",
    "RefreshToken",
    "APIKey",
    "APIKeyUsageLog",
]
