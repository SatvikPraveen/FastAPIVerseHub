# File: app/models/course.py
"""Course catalogue models: courses, lessons, enrollments, reviews, progress."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IntPK, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class DifficultyLevel(enum.StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CourseStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    UNDER_REVIEW = "under_review"


class EnrollmentStatus(enum.StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"
    SUSPENDED = "suspended"


def _enum_column(enum_cls: type[enum.StrEnum], name: str) -> SQLEnum:
    """Store the enum *values* (``"beginner"``) rather than member names.

    This keeps the database representation identical to the API contract and
    lets callers pass either the enum member or its string value.
    """
    return SQLEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class Course(TimestampMixin, Base):
    """Course model for learning resources."""

    __tablename__ = "courses"
    __table_args__ = (Index("ix_courses_published_category", "is_published", "category"),)

    id: Mapped[IntPK]
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(String(500))

    # Course metadata
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None]

    # Course details
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        _enum_column(DifficultyLevel, "difficulty_level"), default=DifficultyLevel.BEGINNER
    )
    estimated_duration_hours: Mapped[int | None]
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Content
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    preview_video_url: Mapped[str | None] = mapped_column(String(500))
    course_outline: Mapped[dict[str, Any] | None]
    learning_objectives: Mapped[list[str] | None]
    prerequisites: Mapped[list[str] | None]

    # Pricing
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_free: Mapped[bool] = mapped_column(default=False)

    # Status and visibility
    status: Mapped[CourseStatus] = mapped_column(
        _enum_column(CourseStatus, "course_status"), default=CourseStatus.DRAFT
    )
    is_published: Mapped[bool] = mapped_column(default=False)
    is_featured: Mapped[bool] = mapped_column(default=False)

    # Analytics and ratings (denormalised counters)
    total_enrollments: Mapped[int] = mapped_column(default=0)
    active_enrollments: Mapped[int] = mapped_column(default=0)
    completion_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    average_rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"))
    total_reviews: Mapped[int] = mapped_column(default=0)

    # SEO
    meta_title: Mapped[str | None] = mapped_column(String(255))
    meta_description: Mapped[str | None] = mapped_column(Text)
    meta_keywords: Mapped[str | None] = mapped_column(String(500))

    # Lifecycle timestamps
    published_at: Mapped[datetime | None]
    last_updated_at: Mapped[datetime | None]

    # Relationships
    instructor: Mapped[User] = relationship(back_populates="courses")
    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="course")
    reviews: Mapped[list[CourseReview]] = relationship(back_populates="course")
    lessons: Mapped[list[Lesson]] = relationship(back_populates="course", order_by="Lesson.order")

    def __repr__(self) -> str:
        return f"<Course(id={self.id}, title='{self.title}', instructor_id={self.instructor_id})>"

    @property
    def is_discounted(self) -> bool:
        return self.original_price is not None and self.price < self.original_price

    @property
    def discount_percentage(self) -> int:
        if not self.is_discounted or not self.original_price:
            return 0
        return int((1 - (self.price / self.original_price)) * 100)

    def get_display_price(self) -> str:
        return "Free" if self.is_free else f"${self.price}"

    def can_be_enrolled(self) -> bool:
        return self.is_published and self.status == CourseStatus.PUBLISHED


class Lesson(TimestampMixin, Base):
    """Lesson model for course content."""

    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("course_id", "slug", name="uq_lessons_course_slug"),)

    id: Mapped[IntPK]
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)

    lesson_type: Mapped[str] = mapped_column(String(50), default="video")
    order: Mapped[int] = mapped_column(default=0)
    duration_minutes: Mapped[int | None]

    video_url: Mapped[str | None] = mapped_column(String(500))
    audio_url: Mapped[str | None] = mapped_column(String(500))
    transcript_url: Mapped[str | None] = mapped_column(String(500))
    attachments: Mapped[list[str] | None]

    is_free_preview: Mapped[bool] = mapped_column(default=False)
    is_published: Mapped[bool] = mapped_column(default=False)

    course: Mapped[Course] = relationship(back_populates="lessons")
    user_progress: Mapped[list[UserLessonProgress]] = relationship(back_populates="lesson")

    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, title='{self.title}', course_id={self.course_id})>"


class Enrollment(Base):
    """Enrollment model for user-course relationships."""

    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),)

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    status: Mapped[EnrollmentStatus] = mapped_column(
        _enum_column(EnrollmentStatus, "enrollment_status"), default=EnrollmentStatus.ACTIVE
    )
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))

    # Payment info (if paid course)
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    payment_currency: Mapped[str | None] = mapped_column(String(3))
    payment_method: Mapped[str | None] = mapped_column(String(50))
    transaction_id: Mapped[str | None] = mapped_column(String(255))

    # Progress tracking
    lessons_completed: Mapped[int] = mapped_column(default=0)
    total_lessons: Mapped[int] = mapped_column(default=0)
    total_time_spent_minutes: Mapped[int] = mapped_column(default=0)
    last_accessed_lesson_id: Mapped[int | None]

    # Completion
    completed_at: Mapped[datetime | None]
    certificate_issued_at: Mapped[datetime | None]
    certificate_url: Mapped[str | None] = mapped_column(String(500))

    # Timestamps (``enrolled_at`` plays the role of ``created_at``)
    enrolled_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment(id={self.id}, user_id={self.user_id}, course_id={self.course_id})>"

    @property
    def is_completed(self) -> bool:
        return self.status == EnrollmentStatus.COMPLETED

    def calculate_progress(self) -> float:
        if self.total_lessons == 0:
            return 0.0
        return (self.lessons_completed / self.total_lessons) * 100


class CourseReview(TimestampMixin, Base):
    """Course review and rating model."""

    __tablename__ = "course_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_course_reviews_user_course"),
    )

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    rating: Mapped[int]  # 1-5 stars
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text)

    is_verified_purchase: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=True)
    is_featured: Mapped[bool] = mapped_column(default=False)

    helpful_count: Mapped[int] = mapped_column(default=0)
    reported_count: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship()
    course: Mapped[Course] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return (
            f"<CourseReview(id={self.id}, user_id={self.user_id}, "
            f"course_id={self.course_id}, rating={self.rating})>"
        )


class UserLessonProgress(TimestampMixin, Base):
    """Track user progress through individual lessons."""

    __tablename__ = "user_lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress_user_lesson"),
    )

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)

    is_completed: Mapped[bool] = mapped_column(default=False)
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    time_spent_minutes: Mapped[int] = mapped_column(default=0)

    last_position_seconds: Mapped[int] = mapped_column(default=0)
    total_duration_seconds: Mapped[int | None]

    completed_at: Mapped[datetime | None]
    first_accessed_at: Mapped[datetime | None]
    last_accessed_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
    lesson: Mapped[Lesson] = relationship(back_populates="user_progress")

    def __repr__(self) -> str:
        return f"<UserLessonProgress(id={self.id}, user_id={self.user_id}, lesson_id={self.lesson_id})>"
