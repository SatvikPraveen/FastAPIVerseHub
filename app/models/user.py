# File: app/models/user.py
"""User-centric models: accounts, uploads, forms, devices and sessions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.models.base import Base, IntPK, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.course import Course, Enrollment


class User(TimestampMixin, SoftDeleteMixin, Base):
    """User model for authentication and profile management."""

    __tablename__ = "users"

    id: Mapped[IntPK]
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))

    # Status fields
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    is_verified: Mapped[bool] = mapped_column(default=False)

    # MFA fields
    mfa_enabled: Mapped[bool] = mapped_column(default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(32))
    backup_codes: Mapped[list[str] | None]

    # Profile fields
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Social auth fields
    github_id: Mapped[str | None] = mapped_column(String(50))
    google_id: Mapped[str | None] = mapped_column(String(50))
    linkedin_id: Mapped[str | None] = mapped_column(String(50))

    # Preferences
    email_notifications: Mapped[bool] = mapped_column(default=True)
    push_notifications: Mapped[bool] = mapped_column(default=True)
    marketing_emails: Mapped[bool] = mapped_column(default=False)

    # Learning preferences
    learning_style: Mapped[str | None] = mapped_column(String(50))
    skill_level: Mapped[str] = mapped_column(String(20), default="beginner")
    interests: Mapped[list[str] | None]

    # Activity tracking
    last_login_at: Mapped[datetime | None]
    last_activity_at: Mapped[datetime | None]
    login_count: Mapped[int] = mapped_column(default=0)

    # Relationships
    courses: Mapped[list[Course]] = relationship(back_populates="instructor")
    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="user")
    file_uploads: Mapped[list[FileUpload]] = relationship(back_populates="user")
    form_submissions: Mapped[list[FormSubmission]] = relationship(back_populates="user")
    device_registrations: Mapped[list[DeviceRegistration]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def is_authenticated(self) -> bool:
        return True

    def has_permission(self, permission: str) -> bool:
        """Superusers hold every permission; finer-grained RBAC can extend this."""
        return bool(self.is_superuser)

    def get_display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    def update_last_activity(self) -> None:
        self.last_activity_at = utcnow()

    def is_online(self, threshold_minutes: int = 5) -> bool:
        if not self.last_activity_at:
            return False
        return self.last_activity_at > utcnow() - timedelta(minutes=threshold_minutes)


class FileUpload(TimestampMixin, SoftDeleteMixin, Base):
    """Model for tracking user file uploads."""

    __tablename__ = "file_uploads"

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int]  # bytes
    content_type: Mapped[str | None] = mapped_column(String(100))
    file_hash: Mapped[str | None] = mapped_column(String(64))  # sha256

    category: Mapped[str] = mapped_column(String(100), default="general")
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    download_count: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="file_uploads")

    def __repr__(self) -> str:
        return f"<FileUpload(id={self.id}, filename='{self.filename}', user_id={self.user_id})>"


class FormSubmission(TimestampMixin, Base):
    """Model for tracking form submissions (contact, feedback, survey, etc.)."""

    __tablename__ = "form_submissions"

    id: Mapped[IntPK]
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # None = anonymous

    form_type: Mapped[str] = mapped_column(String(50))  # contact, feedback, survey, multipart
    data: Mapped[dict[str, Any]]  # serialised form payload
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_anonymous: Mapped[bool] = mapped_column(default=False)

    # Contact-specific
    submitter_name: Mapped[str | None] = mapped_column(String(255))
    submitter_email: Mapped[str | None] = mapped_column(String(255))

    # Survey-specific
    survey_id: Mapped[int | None]
    completion_time_seconds: Mapped[int | None]

    user: Mapped[User | None] = relationship(back_populates="form_submissions")

    def __repr__(self) -> str:
        return (
            f"<FormSubmission(id={self.id}, form_type='{self.form_type}', user_id={self.user_id})>"
        )


class Survey(TimestampMixin, Base):
    """Model for survey definitions."""

    __tablename__ = "surveys"

    id: Mapped[IntPK]
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    questions: Mapped[list[Any]]  # list of question objects
    is_active: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:
        return f"<Survey(id={self.id}, title='{self.title}')>"


class DeviceRegistration(TimestampMixin, Base):
    """Model for tracking a user's registered devices."""

    __tablename__ = "device_registrations"

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    device_name: Mapped[str] = mapped_column(String(100))
    device_type: Mapped[str] = mapped_column(String(50))  # mobile, desktop, tablet
    device_fingerprint: Mapped[str] = mapped_column(String(255))
    device_token: Mapped[str] = mapped_column(String(255), unique=True)

    # Device info
    os_name: Mapped[str | None] = mapped_column(String(50))
    os_version: Mapped[str | None] = mapped_column(String(50))
    browser_name: Mapped[str | None] = mapped_column(String(50))
    browser_version: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Status
    is_trusted: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Activity
    last_used_at: Mapped[datetime | None]
    last_ip_address: Mapped[str | None] = mapped_column(String(45))

    user: Mapped[User] = relationship(back_populates="device_registrations")

    def __repr__(self) -> str:
        return (
            f"<DeviceRegistration(id={self.id}, user_id={self.user_id}, "
            f"device_name='{self.device_name}')>"
        )


class UserSession(TimestampMixin, Base):
    """Model for tracking user sessions."""

    __tablename__ = "user_sessions"

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    session_id: Mapped[str] = mapped_column(String(255), unique=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("device_registrations.id"))

    # Session info
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(default=True)

    last_activity_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
    device: Mapped[DeviceRegistration | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"<UserSession(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}')>"
        )
