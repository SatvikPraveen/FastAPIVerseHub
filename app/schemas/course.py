# File: app/schemas/course.py

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, validator, Field


class CourseBase(BaseModel):
    """Base course schema with common fields."""
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    difficulty: str = Field("beginner", regex="^(beginner|intermediate|advanced|expert)$")
    estimated_duration_hours: Optional[int] = Field(None, ge=0)
    language: str = Field("en", min_length=2, max_length=10)
    tags: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None


class CourseCreate(CourseBase):
    """Schema for creating a new course."""
    price: Optional[Decimal] = Field(Decimal("0.00"), ge=0)
    original_price: Optional[Decimal] = Field(None, ge=0)
    is_free: bool = True
    
    @validator('original_price')
    def original_price_validation(cls, v, values):
        if v is not None and 'price' in values:
            if v < values['price']:
                raise ValueError('Original price cannot be less than current price')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v


class CourseUpdate(BaseModel):
    """Schema for updating course information."""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    difficulty: Optional[str] = Field(None, regex="^(beginner|intermediate|advanced|expert)$")
    estimated_duration_hours: Optional[int] = Field(None, ge=0)
    language: Optional[str] = Field(None, min_length=2, max_length=10)
    tags: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    price: Optional[Decimal] = Field(None, ge=0)
    original_price: Optional[Decimal] = Field(None, ge=0)
    is_free: Optional[bool] = None
    thumbnail_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class CourseResponse(BaseModel):
    """Schema for course response data."""
    id: int
    title: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    instructor_id: int
    instructor_name: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    difficulty: str
    estimated_duration_hours: Optional[int] = None
    language: str
    tags: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    thumbnail_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    price: Decimal
    original_price: Optional[Decimal] = None
    currency: str = "USD"
    is_free: bool = True
    status: str
    is_published: bool
    is_featured: bool = False
    total_enrollments: int = 0
    average_rating: Decimal = Decimal("0.00")
    total_reviews: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CourseWithStats(CourseResponse):
    """Course response with additional statistics."""
    total_enrollments: int = 0
    completed_enrollments: int = 0
    average_rating: float = 0.0
    total_reviews: int = 0
    completion_rate: float = 0.0
    revenue_total: Optional[Decimal] = None
    monthly_enrollments: int = 0


class CourseCard(BaseModel):
    """Simplified course schema for cards/listings."""
    id: int
    title: str
    slug: str
    short_description: Optional[str] = None
    instructor_name: Optional[str] = None
    category: str
    difficulty: str
    estimated_duration_hours: Optional[int] = None
    thumbnail_url: Optional[str] = None
    price: Decimal
    original_price: Optional[Decimal] = None
    is_free: bool
    average_rating: float = 0.0
    total_enrollments: int = 0
    is_featured: bool = False
    
    class Config:
        from_attributes = True


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
    engagement_metrics: Dict[str, Any] = {}
    traffic_sources: Dict[str, int] = {}
    demographics: Dict[str, Any] = {}
    performance_trends: Dict[str, List[float]] = {}
    top_dropout_points: List[Dict[str, Any]] = []


class LessonBase(BaseModel):
    """Base lesson schema."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    lesson_type: str = Field("video", regex="^(video|text|quiz|assignment|live)$")
    duration_minutes: Optional[int] = Field(None, ge=0)
    order: int = Field(0, ge=0)
    is_free_preview: bool = False


class LessonCreate(LessonBase):
    """Schema for creating a lesson."""
    content: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    attachments: Optional[List[str]] = None


class LessonUpdate(BaseModel):
    """Schema for updating a lesson."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content: Optional[str] = None
    lesson_type: Optional[str] = Field(None, regex="^(video|text|quiz|assignment|live)$")
    duration_minutes: Optional[int] = Field(None, ge=0)
    order: Optional[int] = Field(None, ge=0)
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    attachments: Optional[List[str]] = None
    is_free_preview: Optional[bool] = None
    is_published: Optional[bool] = None


class LessonResponse(BaseModel):
    """Schema for lesson response data."""
    id: int
    course_id: int
    title: str
    slug: str
    description: Optional[str] = None
    lesson_type: str
    duration_minutes: Optional[int] = None
    order: int
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    attachments: Optional[List[str]] = None
    is_free_preview: bool
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EnrollmentResponse(BaseModel):
    """Schema for enrollment response data."""
    id: int
    user_id: int
    course_id: int
    course_title: str
    status: str
    progress_percentage: Decimal
    lessons_completed: int
    total_lessons: int
    total_time_spent_minutes: int
    last_accessed_lesson_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    certificate_url: Optional[str] = None
    enrolled_at: datetime
    
    class Config:
        from_attributes = True


class CourseReviewBase(BaseModel):
    """Base course review schema."""
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class CourseReviewCreate(CourseReviewBase):
    """Schema for creating a course review."""
    pass


class CourseReviewUpdate(BaseModel):
    """Schema for updating a course review."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class CourseReviewResponse(BaseModel):
    """Schema for course review response data."""
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    course_id: int
    rating: int
    title: Optional[str] = None
    content: Optional[str] = None
    is_verified_purchase: bool
    helpful_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CourseProgress(BaseModel):
    """Schema for course progress tracking."""
    course_id: int
    user_id: int
    progress_percentage: float = 0.0
    lessons_completed: int = 0
    total_lessons: int = 0
    current_lesson_id: Optional[int] = None
    total_time_spent_minutes: int = 0
    last_accessed_at: Optional[datetime] = None
    estimated_completion_date: Optional[datetime] = None


class LessonProgress(BaseModel):
    """Schema for lesson progress tracking."""
    lesson_id: int
    user_id: int
    is_completed: bool = False
    progress_percentage: float = 0.0
    time_spent_minutes: int = 0
    last_position_seconds: int = 0
    completed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None


class CourseCategory(BaseModel):
    """Schema for course categories."""
    name: str
    slug: str
    description: Optional[str] = None
    course_count: int = 0
    subcategories: List[str] = []
    featured: bool = False


class CourseSearch(BaseModel):
    """Schema for course search parameters."""
    query: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    difficulty: Optional[List[str]] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    duration_min: Optional[int] = None
    duration_max: Optional[int] = None
    rating_min: Optional[float] = None
    language: Optional[str] = None
    is_free: Optional[bool] = None
    tags: Optional[List[str]] = None
    sort_by: Optional[str] = "relevance"
    order: Optional[str] = "desc"