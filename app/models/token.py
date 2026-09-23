# File: app/models/token.py
"""Credential models: generic tokens, refresh-token families and API keys."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.models.base import Base, IntPK, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import DeviceRegistration, User


class TokenType(enum.StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"
    MAGIC_LINK = "magic_link"
    API_KEY = "api_key"


class TokenStatus(enum.StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    USED = "used"


class Token(TimestampMixin, Base):
    """Generic token record (magic links, verification, named tokens...)."""

    __tablename__ = "tokens"

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default=TokenStatus.ACTIVE.value)

    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str] | None]

    expires_at: Mapped[datetime | None]
    last_used_at: Mapped[datetime | None]
    usage_count: Mapped[int] = mapped_column(default=0)
    max_uses: Mapped[int | None]  # None = unlimited

    allowed_ips: Mapped[list[str] | None]
    device_fingerprint: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(Text)

    revoked_at: Mapped[datetime | None]
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    revoked_by_user: Mapped[User | None] = relationship(foreign_keys=[revoked_by])

    def __repr__(self) -> str:
        return (
            f"<Token(id={self.id}, user_id={self.user_id}, "
            f"type='{self.token_type}', status='{self.status}')>"
        )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and utcnow() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.status == TokenStatus.REVOKED

    @property
    def is_valid(self) -> bool:
        if self.is_expired or self.is_revoked:
            return False
        return not (self.max_uses and self.usage_count >= self.max_uses)

    def revoke(self, revoked_by_user_id: int | None = None, reason: str | None = None) -> None:
        self.status = TokenStatus.REVOKED.value
        self.revoked_at = utcnow()
        self.revoked_by = revoked_by_user_id
        self.revocation_reason = reason

    def increment_usage(self) -> None:
        self.usage_count += 1
        self.last_used_at = utcnow()
        if self.max_uses and self.usage_count >= self.max_uses:
            self.status = TokenStatus.USED.value

    def can_be_used_from_ip(self, ip_address: str) -> bool:
        return not self.allowed_ips or ip_address in self.allowed_ips

    def has_scope(self, required_scope: str) -> bool:
        return not self.scopes or required_scope in self.scopes


class RefreshToken(TimestampMixin, Base):
    """Refresh token with rotation lineage (``token_family`` / ``parent_token``)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_active", "user_id", "is_revoked"),)

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    jti: Mapped[str] = mapped_column(String(255), unique=True)

    device_id: Mapped[int | None] = mapped_column(ForeignKey("device_registrations.id"))
    session_id: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    issued_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    last_used_at: Mapped[datetime | None]

    is_revoked: Mapped[bool] = mapped_column(default=False)
    revoked_at: Mapped[datetime | None]
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    token_family: Mapped[str | None] = mapped_column(String(255), index=True)
    parent_token_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_tokens.id"))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    device: Mapped[DeviceRegistration | None] = relationship()
    revoked_by_user: Mapped[User | None] = relationship(foreign_keys=[revoked_by])
    parent_token: Mapped[RefreshToken | None] = relationship(
        remote_side="RefreshToken.id", back_populates="child_tokens"
    )
    child_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="parent_token")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, jti='{self.jti}')>"

    @property
    def is_expired(self) -> bool:
        return utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked and not self.is_expired

    def revoke(self, revoked_by_user_id: int | None = None) -> None:
        self.is_revoked = True
        self.revoked_at = utcnow()
        self.revoked_by = revoked_by_user_id


class APIKey(TimestampMixin, Base):
    """API key with scopes, allow-lists and rolling usage counters."""

    __tablename__ = "api_keys"

    id: Mapped[IntPK]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    scopes: Mapped[list[str]]
    rate_limit_per_hour: Mapped[int] = mapped_column(default=1000)
    rate_limit_per_day: Mapped[int] = mapped_column(default=10000)

    last_used_at: Mapped[datetime | None]
    usage_count: Mapped[int] = mapped_column(default=0)
    daily_usage_count: Mapped[int] = mapped_column(default=0)
    hourly_usage_count: Mapped[int] = mapped_column(default=0)
    last_usage_reset: Mapped[datetime | None] = mapped_column(server_default=func.now())

    allowed_ips: Mapped[list[str] | None]
    allowed_domains: Mapped[list[str] | None]

    is_active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
    usage_logs: Mapped[list[APIKeyUsageLog]] = relationship(back_populates="api_key")

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def can_make_request(self, ip_address: str | None = None, domain: str | None = None) -> bool:
        if not self.is_valid:
            return False
        if self.allowed_ips and ip_address and ip_address not in self.allowed_ips:
            return False
        if self.allowed_domains and domain and domain not in self.allowed_domains:
            return False
        if self.hourly_usage_count >= self.rate_limit_per_hour:
            return False
        return self.daily_usage_count < self.rate_limit_per_day

    def increment_usage(self) -> None:
        """Bump counters, rolling the hourly/daily windows when they lapse."""
        now = utcnow()
        if self.last_usage_reset:
            elapsed = now - self.last_usage_reset
            if elapsed >= timedelta(hours=1):
                self.hourly_usage_count = 0
            if elapsed >= timedelta(days=1):
                self.daily_usage_count = 0
                self.last_usage_reset = now
        else:
            self.last_usage_reset = now

        self.usage_count += 1
        self.hourly_usage_count += 1
        self.daily_usage_count += 1
        self.last_used_at = now


class APIKeyUsageLog(Base):
    """Per-request audit log for API keys."""

    __tablename__ = "api_key_usage_logs"
    __table_args__ = (Index("ix_api_key_usage_logs_key_created", "api_key_id", "created_at"),)

    id: Mapped[IntPK]
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))

    endpoint: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int]
    response_time_ms: Mapped[int | None]

    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    referer: Mapped[str | None] = mapped_column(String(500))

    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    api_key: Mapped[APIKey] = relationship(back_populates="usage_logs")

    def __repr__(self) -> str:
        return (
            f"<APIKeyUsageLog(id={self.id}, api_key_id={self.api_key_id}, "
            f"endpoint='{self.endpoint}')>"
        )
