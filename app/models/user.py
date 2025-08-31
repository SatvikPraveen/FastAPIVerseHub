# File: app/models/user.py

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model for authentication and profile management."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Status fields
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    # MFA fields
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(32), nullable=True)
    backup_codes = Column(JSON, nullable=True)
    
    # Profile fields
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    location = Column(String(100), nullable=True)
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    
    # Social auth fields
    github_id = Column(String(50), nullable=True)
    google_id = Column(String(50), nullable=True)
    linkedin_id = Column(String(50), nullable=True)
    
    # Preferences
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    marketing_emails = Column(Boolean, default=False)
    
    # Learning preferences
    learning_style = Column(String(50), nullable=True)
    skill_level = Column(String(20), default="beginner")
    interests = Column(JSON, nullable=True)  # List of interests
    
    # Activity tracking
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    courses = relationship("Course", back_populates="instructor")
    enrollments = relationship("Enrollment", back_populates="user")
    file_uploads = relationship("FileUpload", back_populates="user")
    form_submissions = relationship("FormSubmission", back_populates="user")
    device_registrations = relationship("DeviceRegistration", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"
    
    @property
    def is_anonymous(self) -> bool:
        """Check if user is anonymous."""
        return False
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return True
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        if self.is_superuser:
            return True
        
        # Add more specific permission logic here
        return False
    
    def get_display_name(self) -> str:
        """Get user's display name."""
        return self.full_name or self.email.split("@")[0]
    
    def update_last_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()
    
    def is_online(self, threshold_minutes: int = 5) -> bool:
        """Check if user is currently online."""
        if not self.last_activity_at:
            return False
        
        threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        return self.last_activity_at > threshold


class DeviceRegistration(Base):
    """Model for tracking user's registered devices."""
    
    __tablename__ = "device_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    device_name = Column(String(100), nullable=False)
    device_type = Column(String(50), nullable=False)  # mobile, desktop, tablet
    device_fingerprint = Column(String(255), nullable=False)
    device_token = Column(String(255), nullable=False, unique=True)
    
    # Device info
    os_name = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    browser_name = Column(String(50), nullable=True)
    browser_version = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Status
    is_trusted = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Activity
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_ip_address = Column(String(45), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="device_registrations")
    
    def __repr__(self):
        return f"<DeviceRegistration(id={self.id}, user_id={self.user_id}, device_name='{self.device_name}')>"


class UserSession(Base):
    """Model for tracking user sessions."""
    
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    session_id = Column(String(255), nullable=False, unique=True)
    device_id = Column(Integer, ForeignKey("device_registrations.id"), nullable=True)
    
    # Session info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Activity
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    device = relationship("DeviceRegistration")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}')>"