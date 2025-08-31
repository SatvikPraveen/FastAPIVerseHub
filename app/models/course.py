# File: app/models/course.py

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, 
    ForeignKey, Numeric, JSON, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class DifficultyLevel(str, enum.Enum):
    """Course difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate" 
    ADVANCED = "advanced"
    EXPERT = "expert"


class CourseStatus(str, enum.Enum):
    """Course status options."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    UNDER_REVIEW = "under_review"


class EnrollmentStatus(str, enum.Enum):
    """Enrollment status options."""
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"
    SUSPENDED = "suspended"


class Course(Base):
    """Course model for learning resources."""
    
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)
    
    # Course metadata
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    
    # Course details
    difficulty = Column(SQLEnum(DifficultyLevel), default=DifficultyLevel.BEGINNER)
    estimated_duration_hours = Column(Integer, nullable=True)
    language = Column(String(10), default="en")
    
    # Content
    thumbnail_url = Column(String(500), nullable=True)
    preview_video_url = Column(String(500), nullable=True)
    course_outline = Column(JSON, nullable=True)  # Structured course content
    learning_objectives = Column(JSON, nullable=True)  # List of objectives
    prerequisites = Column(JSON, nullable=True)  # List of prerequisites
    
    # Pricing
    price = Column(Numeric(10, 2), default=0.00)
    original_price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), default="USD")
    is_free = Column(Boolean, default=False)
    
    # Status and visibility
    status = Column(SQLEnum(CourseStatus), default=CourseStatus.DRAFT)
    is_published = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    
    # Analytics and ratings
    total_enrollments = Column(Integer, default=0)
    active_enrollments = Column(Integer, default=0)
    completion_rate = Column(Numeric(5, 2), default=0.00)  # Percentage
    average_rating = Column(Numeric(3, 2), default=0.00)
    total_reviews = Column(Integer, default=0)
    
    # SEO
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    
    # Timestamps
    published_at = Column(DateTime(timezone=True), nullable=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    instructor = relationship("User", back_populates="courses")
    enrollments = relationship("Enrollment", back_populates="course")
    reviews = relationship("CourseReview", back_populates="course")
    lessons = relationship("Lesson", back_populates="course")
    
    def __repr__(self):
        return f"<Course(id={self.id}, title='{self.title}', instructor_id={self.instructor_id})>"
    
    @property
    def is_discounted(self) -> bool:
        """Check if course has a discount."""
        return self.original_price and self.price < self.original_price
    
    @property
    def discount_percentage(self) -> int:
        """Calculate discount percentage."""
        if not self.is_discounted:
            return 0
        return int((1 - (self.price / self.original_price)) * 100)
    
    def get_display_price(self) -> str:
        """Get formatted price for display."""
        if self.is_free:
            return "Free"
        return f"${self.price}"
    
    def can_be_enrolled(self) -> bool:
        """Check if course can be enrolled in."""
        return self.is_published and self.status == CourseStatus.PUBLISHED
    
    def update_enrollment_stats(self) -> None:
        """Update enrollment statistics."""
        # This would be called when enrollment changes
        pass


class Lesson(Base):
    """Lesson model for course content."""
    
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    
    # Lesson metadata
    lesson_type = Column(String(50), default="video")  # video, text, quiz, assignment
    order = Column(Integer, nullable=False, default=0)
    duration_minutes = Column(Integer, nullable=True)
    
    # Content URLs
    video_url = Column(String(500), nullable=True)
    audio_url = Column(String(500), nullable=True)
    transcript_url = Column(String(500), nullable=True)
    attachments = Column(JSON, nullable=True)  # List of attachment URLs
    
    # Settings
    is_free_preview = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    course = relationship("Course", back_populates="lessons")
    user_progress = relationship("UserLessonProgress", back_populates="lesson")
    
    def __repr__(self):
        return f"<Lesson(id={self.id}, title='{self.title}', course_id={self.course_id})>"


class Enrollment(Base):
    """Enrollment model for user-course relationships."""
    
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    # Enrollment details
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE)
    progress_percentage = Column(Numeric(5, 2), default=0.00)
    
    # Payment info (if paid course)
    payment_amount = Column(Numeric(10, 2), nullable=True)
    payment_currency = Column(String(3), nullable=True)
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(255), nullable=True)
    
    # Progress tracking
    lessons_completed = Column(Integer, default=0)
    total_lessons = Column(Integer, default=0)
    total_time_spent_minutes = Column(Integer, default=0)
    last_accessed_lesson_id = Column(Integer, nullable=True)
    
    # Completion
    completed_at = Column(DateTime(timezone=True), nullable=True)
    certificate_issued_at = Column(DateTime(timezone=True), nullable=True)
    certificate_url = Column(String(500), nullable=True)
    
    # Timestamps
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    
    def __repr__(self):
        return f"<Enrollment(id={self.id}, user_id={self.user_id}, course_id={self.course_id})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if enrollment is completed."""
        return self.status == EnrollmentStatus.COMPLETED
    
    def calculate_progress(self) -> float:
        """Calculate current progress percentage."""
        if self.total_lessons == 0:
            return 0.0
        return (self.lessons_completed / self.total_lessons) * 100


class CourseReview(Base):
    """Course review and rating model."""
    
    __tablename__ = "course_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    
    # Review content
    rating = Column(Integer, nullable=False)  # 1-5 stars
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    
    # Review metadata
    is_verified_purchase = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    
    # Interaction
    helpful_count = Column(Integer, default=0)
    reported_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    course = relationship("Course", back_populates="reviews")
    
    def __repr__(self):
        return f"<CourseReview(id={self.id}, user_id={self.user_id}, course_id={self.course_id}, rating={self.rating})>"


class UserLessonProgress(Base):
    """Track user progress through individual lessons."""
    
    __tablename__ = "user_lesson_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    
    # Progress tracking
    is_completed = Column(Boolean, default=False)
    progress_percentage = Column(Numeric(5, 2), default=0.00)
    time_spent_minutes = Column(Integer, default=0)
    
    # Video/Audio progress
    last_position_seconds = Column(Integer, default=0)
    total_duration_seconds = Column(Integer, nullable=True)
    
    # Completion details
    completed_at = Column(DateTime(timezone=True), nullable=True)
    first_accessed_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    lesson = relationship("Lesson", back_populates="user_progress")
    
    def __repr__(self):
        return f"<UserLessonProgress(id={self.id}, user_id={self.user_id}, lesson_id={self.lesson_id})>"