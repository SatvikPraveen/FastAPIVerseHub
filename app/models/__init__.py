# File: app/models/__init__.py
"""
Import all models here so that Base.metadata is fully populated
before any call to Base.metadata.create_all() or Alembic migrations.
"""

from app.models.base import Base

# Course-side models
from app.models.course import (
    Course,
    CourseReview,
    Enrollment,
    Lesson,
    UserLessonProgress,
)

# Token models
from app.models.token import (
    APIKey,
    APIKeyUsageLog,
    RefreshToken,
    Token,
)

# User-side models
from app.models.user import (
    DeviceRegistration,
    FileUpload,
    FormSubmission,
    Survey,
    User,
    UserSession,
)

__all__ = [
    "APIKey",
    "APIKeyUsageLog",
    "Base",
    "Course",
    "CourseReview",
    "DeviceRegistration",
    "Enrollment",
    "FileUpload",
    "FormSubmission",
    "Lesson",
    "RefreshToken",
    "Survey",
    "Token",
    "User",
    "UserLessonProgress",
    "UserSession",
]
