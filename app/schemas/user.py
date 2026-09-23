# File: app/schemas/user.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    full_name: str | None = None
    bio: str | None = None
    phone: str | None = None
    location: str | None = None
    timezone: str | None = None
    language: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    marketing_emails: bool | None = None
    learning_style: str | None = None
    skill_level: str | None = None
    interests: list[str] | None = None


class UserResponse(BaseModel):
    """Schema for user response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    bio: str | None = None
    phone: str | None = None
    location: str | None = None
    timezone: str = "UTC"
    language: str = "en"
    avatar_url: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    mfa_enabled: bool = False
    email_notifications: bool = True
    push_notifications: bool = True
    marketing_emails: bool = False
    learning_style: str | None = None
    skill_level: str = "beginner"
    interests: list[str] | None = None
    last_login_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserProfile(BaseModel):
    """Extended user profile schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    location: str | None = None
    timezone: str
    language: str
    learning_style: str | None = None
    skill_level: str
    interests: list[str] | None = None
    total_courses: int = 0
    completed_courses: int = 0
    certificates_earned: int = 0
    total_learning_hours: int = 0
    streak_days: int = 0
    achievements: list[str] = []
    social_links: dict | None = None
    joined_date: datetime


class UserStats(BaseModel):
    """User statistics schema."""

    total_courses: int = 0
    completed_courses: int = 0
    in_progress_courses: int = 0
    total_uploads: int = 0
    account_age_days: int = 0
    last_activity: datetime | None = None
    learning_streak: int = 0
    total_study_time_hours: int = 0
    average_course_rating: float | None = None
    certificates_earned: int = 0
    badges_earned: list[str] = []


class UserPreferences(BaseModel):
    """User preferences schema."""

    email_notifications: bool = True
    push_notifications: bool = True
    marketing_emails: bool = False
    learning_reminders: bool = True
    course_updates: bool = True
    social_features: bool = True
    public_profile: bool = True
    show_progress: bool = True
    theme: str = "light"
    language: str = "en"
    timezone: str = "UTC"
    notification_frequency: str = "daily"


class PasswordChangeRequest(BaseModel):
    """Schema for password change requests."""

    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str, info) -> str:
        if "current_password" in info.data and v == info.data["current_password"]:
            raise ValueError("New password must be different from current password")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return v


class EmailUpdateRequest(BaseModel):
    """Schema for email update requests."""

    new_email: EmailStr
    password: str


class UserSearchResult(BaseModel):
    """Schema for user search results."""

    id: int
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    location: str | None = None
    total_courses: int = 0
    average_rating: float | None = None
    specialties: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class UserActivity(BaseModel):
    """Schema for user activity tracking."""

    user_id: int
    activity_type: str
    description: str
    metadata: dict | None = None
    timestamp: datetime
    ip_address: str | None = None
    user_agent: str | None = None


class UserAchievement(BaseModel):
    """Schema for user achievements."""

    id: int
    title: str
    description: str
    icon_url: str | None = None
    category: str
    points: int = 0
    earned_at: datetime
    is_featured: bool = False


class UserBadge(BaseModel):
    """Schema for user badges."""

    id: int
    name: str
    description: str
    image_url: str | None = None
    rarity: str = "common"  # common, rare, epic, legendary
    earned_at: datetime
    progress: dict | None = None


class UserLearningPath(BaseModel):
    """Schema for user's learning path progress."""

    path_id: int
    path_title: str
    total_courses: int
    completed_courses: int
    current_course_id: int | None = None
    progress_percentage: float = 0.0
    estimated_completion_date: datetime | None = None
    started_at: datetime
    last_activity_at: datetime | None = None
