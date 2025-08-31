# File: app/models/token.py

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class TokenType(str, enum.Enum):
    """Token type enumeration."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"
    MAGIC_LINK = "magic_link"
    API_KEY = "api_key"


class TokenStatus(str, enum.Enum):
    """Token status enumeration."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    USED = "used"


class Token(Base):
    """Token model for managing various authentication tokens."""
    
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Token details
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    token_type = Column(String(50), nullable=False)
    status = Column(String(20), default="active")
    
    # Token metadata
    name = Column(String(255), nullable=True)  # For API keys or named tokens
    description = Column(Text, nullable=True)
    scopes = Column(JSON, nullable=True)  # List of permitted scopes
    
    # Expiration and usage
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)
    max_uses = Column(Integer, nullable=True)  # Null = unlimited
    
    # IP and device restrictions
    allowed_ips = Column(JSON, nullable=True)  # List of allowed IP addresses
    device_fingerprint = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Revocation
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    revocation_reason = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by])
    
    def __repr__(self):
        return f"<Token(id={self.id}, user_id={self.user_id}, type='{self.token_type}', status='{self.status}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_revoked(self) -> bool:
        """Check if token is revoked."""
        return self.status == TokenStatus.REVOKED
    
    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not revoked, usage limits)."""
        if self.is_expired or self.is_revoked:
            return False
        
        if self.max_uses and self.usage_count >= self.max_uses:
            return False
        
        return True
    
    def revoke(self, revoked_by_user_id: Optional[int] = None, reason: Optional[str] = None) -> None:
        """Revoke the token."""
        self.status = TokenStatus.REVOKED
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by_user_id
        self.revocation_reason = reason
    
    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
        
        # Auto-revoke if max uses reached
        if self.max_uses and self.usage_count >= self.max_uses:
            self.status = TokenStatus.USED
    
    def can_be_used_from_ip(self, ip_address: str) -> bool:
        """Check if token can be used from given IP address."""
        if not self.allowed_ips:
            return True  # No IP restrictions
        
        return ip_address in self.allowed_ips
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if token has required scope."""
        if not self.scopes:
            return True  # No scope restrictions
        
        return required_scope in self.scopes


class RefreshToken(Base):
    """Dedicated model for refresh tokens with additional tracking."""
    
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Token details
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    jti = Column(String(255), nullable=False, unique=True)  # JWT ID
    
    # Device and session info
    device_id = Column(Integer, ForeignKey("device_registrations.id"), nullable=True)
    session_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Token lifecycle
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Token family for rotation
    token_family = Column(String(255), nullable=True, index=True)
    parent_token_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    device = relationship("DeviceRegistration")
    revoked_by_user = relationship("User", foreign_keys=[revoked_by])
    parent_token = relationship("RefreshToken", remote_side=[id])
    child_tokens = relationship("RefreshToken", remote_side=[parent_token_id])
    
    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, jti='{self.jti}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if refresh token is expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if refresh token is valid."""
        return not self.is_revoked and not self.is_expired
    
    def revoke(self, revoked_by_user_id: Optional[int] = None) -> None:
        """Revoke the refresh token."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by_user_id
    
    def revoke_family(self) -> None:
        """Revoke entire token family (for security breach detection)."""
        # This would revoke all tokens in the same family
        pass


class APIKey(Base):
    """Model for API keys with advanced management features."""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Key details
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(10), nullable=False)  # First few chars for identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions and scopes
    scopes = Column(JSON, nullable=False)  # List of allowed scopes
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    
    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0)
    daily_usage_count = Column(Integer, default=0)
    hourly_usage_count = Column(Integer, default=0)
    last_usage_reset = Column(DateTime(timezone=True), server_default=func.now())
    
    # Restrictions
    allowed_ips = Column(JSON, nullable=True)  # List of allowed IPs
    allowed_domains = Column(JSON, nullable=True)  # List of allowed domains
    
    # Status and expiration
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    usage_logs = relationship("APIKeyUsageLog", back_populates="api_key")
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if API key is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if API key is valid."""
        return self.is_active and not self.is_expired
    
    def can_make_request(self, ip_address: Optional[str] = None, domain: Optional[str] = None) -> bool:
        """Check if API key can make request from given IP/domain."""
        if not self.is_valid:
            return False
        
        # Check IP restrictions
        if self.allowed_ips and ip_address:
            if ip_address not in self.allowed_ips:
                return False
        
        # Check domain restrictions
        if self.allowed_domains and domain:
            if domain not in self.allowed_domains:
                return False
        
        # Check rate limits
        if self.hourly_usage_count >= self.rate_limit_per_hour:
            return False
        
        if self.daily_usage_count >= self.rate_limit_per_day:
            return False
        
        return True
    
    def increment_usage(self) -> None:
        """Increment usage counters."""
        now = datetime.utcnow()
        
        # Reset counters if needed
        if self.last_usage_reset:
            if (now - self.last_usage_reset).seconds >= 3600:  # 1 hour
                self.hourly_usage_count = 0
            
            if (now - self.last_usage_reset).days >= 1:  # 1 day
                self.daily_usage_count = 0
                self.last_usage_reset = now
        
        # Increment counters
        self.usage_count += 1
        self.hourly_usage_count += 1
        self.daily_usage_count += 1
        self.last_used_at = now


class APIKeyUsageLog(Base):
    """Log API key usage for analytics and monitoring."""
    
    __tablename__ = "api_key_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)
    
    # Request details
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    
    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referer = Column(String(500), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    api_key = relationship("APIKey", back_populates="usage_logs")
    
    def __repr__(self):
        return f"<APIKeyUsageLog(id={self.id}, api_key_id={self.api_key_id}, endpoint='{self.endpoint}')>"