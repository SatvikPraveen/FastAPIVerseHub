# File: app/schemas/course.py

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseBase(BaseModel):
    """Base course schema with common fields."""

    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = None
    short_description: str | None = Field(None, max_length=500)
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: str | None = Field(None, max_length=100)
    difficulty: str = Field("beginner", pattern="^(beginner|intermediate|advanced|expert)$")
    estimated_duration_hours: int | None = Field(None, ge=0)
    language: str = Field("en", min_length=2, max_length=10)
    tags: list[str] | None = None
    learning_objectives: list[str] | None = None
    prerequisites: list[str] | None = None


class CourseCreate(CourseBase):
    """Schema for creating a new course."""

    price: Decimal | None = Field(Decimal("0.00"), ge=0)
    original_price: Decimal | None = Field(None, ge=0)
    is_free: bool = True

    @field_validator("original_price")
    @classmethod
    def original_price_validation(cls, v, info):
        if v is not None and "price" in info.data and v < info.data["price"]:
            raise ValueError("Original price cannot be less than current price")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return v


class CourseUpdate(BaseModel):
    """Schema for updating course information."""

    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = None
    short_description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, min_length=1, max_length=100)
    subcategory: str | None = Field(None, max_length=100)
    difficulty: str | None = Field(None, pattern="^(beginner|intermediate|advanced|expert)$")
    estimated_duration_hours: int | None = Field(None, ge=0)
    language: str | None = Field(None, min_length=2, max_length=10)
    tags: list[str] | None = None
    learning_objectives: list[str] | None = None
    prerequisites: list[str] | None = None
    price: Decimal | None = Field(None, ge=0)
    original_price: Decimal | None = Field(None, ge=0)
    is_free: bool | None = None
    thumbnail_url: str | None = None
    preview_video_url: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None


class CourseResponse(BaseModel):
    """Schema for course response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str | None = None
    short_description: str | None = None
    instructor_id: int
    instructor_name: str | None = None
    category: str
    subcategory: str | None = None
    difficulty: str
    estimated_duration_hours: int | None = None
    language: str
    tags: list[str] | None = None
    learning_objectives: list[str] | None = None
    prerequisites: list[str] | None = None
    thumbnail_url: str | None = None
    preview_video_url: str | None = None
    price: Decimal
    original_price: Decimal | None = None
    currency: str = "USD"
    is_free: bool = True
    status: str
    is_published: bool
    is_featured: bool = False
    total_enrollments: int = 0
    average_rating: Decimal = Decimal("0.00")
    total_reviews: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None


class CourseWithStats(CourseResponse):
    """Course response with additional statistics."""

    total_enrollments: int = 0
    completed_enrollments: int = 0
    average_rating: Decimal = Decimal("0.00")
    total_reviews: int = 0
    completion_rate: float = 0.0
    revenue_total: Decimal | None = None
    monthly_enrollments: int = 0


class CourseCard(BaseModel):
    """Simplified course schema for cards/listings."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    short_description: str | None = None
    instructor_name: str | None = None
    category: str
    difficulty: str
    estimated_duration_hours: int | None = None
    thumbnail_url: str | None = None
    price: Decimal
    original_price: Decimal | None = None
    is_free: bool
    average_rating: float = 0.0
    total_enrollments: int = 0
    is_featured: bool = False


class CourseAnalytics(BaseModel):
    """Schema for course analytics data."""

    course_id: int
    total_views: int = 0
    total_enrollments: int = 0
    conversion_rate: float = 0.0
    completion_rate: float = 0.0
    average_rating: float = 0.0
    total_reviews: int = 0
    revenue_total: Decimal = Decimal("0.00")
    revenue_monthly: Decimal = Decimal("0.00")
    refund_rate: float = 0.0
    student_satisfaction: float = 0.0
    engagement_metrics: dict[str, Any] = {}
    traffic_sources: dict[str, int] = {}
    demographics: dict[str, Any] = {}
    performance_trends: dict[str, list[float]] = {}
    top_dropout_points: list[dict[str, Any]] = []


class LessonBase(BaseModel):
    """Base lesson schema."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    lesson_type: str = Field("video", pattern="^(video|text|quiz|assignment|live)$")
    duration_minutes: int | None = Field(None, ge=0)
    order: int = Field(0, ge=0)
    is_free_preview: bool = False


class LessonCreate(LessonBase):
    """Schema for creating a lesson."""

    content: str | None = None
    video_url: str | None = None
    audio_url: str | None = None
    attachments: list[str] | None = None


class LessonUpdate(BaseModel):
    """Schema for updating a lesson."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    content: str | None = None
    lesson_type: str | None = Field(None, pattern="^(video|text|quiz|assignment|live)$")
    duration_minutes: int | None = Field(None, ge=0)
    order: int | None = Field(None, ge=0)
    video_url: str | None = None
    audio_url: str | None = None
    attachments: list[str] | None = None
    is_free_preview: bool | None = None
    is_published: bool | None = None


class LessonResponse(BaseModel):
    """Schema for lesson response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    slug: str
    description: str | None = None
    lesson_type: str
    duration_minutes: int | None = None
    order: int
    video_url: str | None = None
    audio_url: str | None = None
    attachments: list[str] | None = None
    is_free_preview: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime | None = None


class EnrollmentResponse(BaseModel):
    """Schema for enrollment response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    course_id: int
    course_title: str
    status: str
    progress_percentage: Decimal
    lessons_completed: int
    total_lessons: int
    total_time_spent_minutes: int
    last_accessed_lesson_id: int | None = None
    completed_at: datetime | None = None
    certificate_url: str | None = None
    enrolled_at: datetime


class CourseReviewBase(BaseModel):
    """Base course review schema."""

    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(None, max_length=255)
    content: str | None = None


class CourseReviewCreate(CourseReviewBase):
    """Schema for creating a course review."""


class CourseReviewUpdate(BaseModel):
    """Schema for updating a course review."""

    rating: int | None = Field(None, ge=1, le=5)
    title: str | None = Field(None, max_length=255)
    content: str | None = None


class CourseReviewResponse(BaseModel):
    """Schema for course review response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_name: str | None = None
    user_avatar: str | None = None
    course_id: int
    rating: int
    title: str | None = None
    content: str | None = None
    is_verified_purchase: bool
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class CourseProgress(BaseModel):
    """Schema for course progress tracking."""

    course_id: int
    user_id: int
    progress_percentage: float = 0.0
    lessons_completed: int = 0
    total_lessons: int = 0
    current_lesson_id: int | None = None
    total_time_spent_minutes: int = 0
    last_accessed_at: datetime | None = None
    estimated_completion_date: datetime | None = None


class LessonProgress(BaseModel):
    """Schema for lesson progress tracking."""

    lesson_id: int
    user_id: int
    is_completed: bool = False
    progress_percentage: float = 0.0
    time_spent_minutes: int = 0
    last_position_seconds: int = 0
    completed_at: datetime | None = None
    last_accessed_at: datetime | None = None


class CourseCategory(BaseModel):
    """Schema for course categories."""

    name: str
    slug: str
    description: str | None = None
    course_count: int = 0
    subcategories: list[str] = []
    featured: bool = False


class CourseSearch(BaseModel):
    """Schema for course search parameters."""

    query: str | None = None
    category: str | None = None
    subcategory: str | None = None
    difficulty: list[str] | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    duration_min: int | None = None
    duration_max: int | None = None
    rating_min: float | None = None
    language: str | None = None
    is_free: bool | None = None
    tags: list[str] | None = None
    sort_by: str | None = "relevance"
    order: str | None = "desc"
