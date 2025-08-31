# File: app/schemas/user.py

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, validator


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    learning_style: Optional[str] = None
    skill_level: Optional[str] = None
    interests: Optional[List[str]] = None


class UserResponse(BaseModel):
    """Schema for user response data."""
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    avatar_url: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    mfa_enabled: bool = False
    email_notifications: bool = True
    push_notifications: bool = True
    marketing_emails: bool = False
    learning_style: Optional[str] = None
    skill_level: str = "beginner"
    interests: Optional[List[str]] = None
    last_login_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """Extended user profile schema."""
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    timezone: str
    language: str
    learning_style: Optional[str] = None
    skill_level: str
    interests: Optional[List[str]] = None
    total_courses: int = 0
    completed_courses: int = 0
    certificates_earned: int = 0
    total_learning_hours: int = 0
    streak_days: int = 0
    achievements: List[str] = []
    social_links: Optional[dict] = None
    joined_date: datetime
    
    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """User statistics schema."""
    total_courses: int = 0
    completed_courses: int = 0
    in_progress_courses: int = 0
    total_uploads: int = 0
    account_age_days: int = 0
    last_activity: Optional[datetime] = None
    learning_streak: int = 0
    total_study_time_hours: int = 0
    average_course_rating: Optional[float] = None
    certificates_earned: int = 0
    badges_earned: List[str] = []


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
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('New passwords do not match')
        return v
    
    @validator('new_password')
    def validate_new_password(cls, v, values, **kwargs):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class EmailUpdateRequest(BaseModel):
    """Schema for email update requests."""
    new_email: EmailStr
    password: str


class UserSearchResult(BaseModel):
    """Schema for user search results."""
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    total_courses: int = 0
    average_rating: Optional[float] = None
    specialties: List[str] = []
    
    class Config:
        from_attributes = True


class UserActivity(BaseModel):
    """Schema for user activity tracking."""
    user_id: int
    activity_type: str
    description: str
    metadata: Optional[dict] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class UserAchievement(BaseModel):
    """Schema for user achievements."""
    id: int
    title: str
    description: str
    icon_url: Optional[str] = None
    category: str
    points: int = 0
    earned_at: datetime
    is_featured: bool = False


class UserBadge(BaseModel):
    """Schema for user badges."""
    id: int
    name: str
    description: str
    image_url: Optional[str] = None
    rarity: str = "common"  # common, rare, epic, legendary
    earned_at: datetime
    progress: Optional[dict] = None


class UserLearningPath(BaseModel):
    """Schema for user's learning path progress."""
    path_id: int
    path_title: str
    total_courses: int
    completed_courses: int
    current_course_id: Optional[int] = None
    progress_percentage: float = 0.0
    estimated_completion_date: Optional[datetime] = None
    started_at: datetime
    last_activity_at: Optional[datetime] = None