# File: app/core/security.py

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings

# bcrypt silently truncated passwords at 72 bytes for years; bcrypt>=5 now
# raises instead.  We reject over-long passwords explicitly so the failure is
# deterministic and surfaces as a validation error rather than a 500.
BCRYPT_MAX_PASSWORD_BYTES = 72

# JWT token bearer
security = HTTPBearer()


class PasswordHasher:
    """Thin, dependency-free wrapper around bcrypt.

    Replaces ``passlib`` which is unmaintained and incompatible with
    bcrypt >= 4.1.  Hash format is unchanged (``$2b$``), so existing rows
    keep verifying.
    """

    def __init__(self, rounds: int = 12):
        self.rounds = rounds

    @staticmethod
    def _to_bytes(password: str) -> bytes:
        raw = password.encode("utf-8")
        if len(raw) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password cannot exceed {BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded"
            )
        return raw

    def hash(self, password: str) -> str:
        return bcrypt.hashpw(self._to_bytes(password), bcrypt.gensalt(self.rounds)).decode("ascii")

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(self._to_bytes(password), hashed.encode("ascii"))
        except (ValueError, TypeError):
            # Malformed hash or over-long password: never raise from verify.
            return False

    def needs_rehash(self, hashed: str) -> bool:
        """True when the stored hash uses fewer rounds than currently configured."""
        try:
            return int(hashed.split("$")[2]) < self.rounds
        except (IndexError, ValueError):
            return True


password_hasher = PasswordHasher()


class SecurityManager:
    """Centralized security management for the application."""

    def __init__(self) -> None:
        self.hasher = password_hasher
        self.algorithm = settings.JWT_ALGORITHM
        self.secret_key = settings.JWT_SECRET_KEY.get_secret_value()

    # Password operations
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        return self.hasher.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.hasher.hash(password)

    # JWT token operations
    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update(
            {"exp": expire, "iat": datetime.now(UTC), "type": "access", "jti": str(uuid.uuid4())}
        )

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return encoded_jwt

    def create_refresh_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update(
            {"exp": expire, "iat": datetime.now(UTC), "type": "refresh", "jti": str(uuid.uuid4())}
        )

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return encoded_jwt

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            return payload

        except ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    @staticmethod
    def subject_id(payload: dict[str, Any]) -> int:
        """Return the integer user id carried in the ``sub`` claim, or raise 401."""
        sub = payload.get("sub")
        try:
            return int(str(sub))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    def get_user_id_from_token(self, token: str) -> int:
        """Extract user ID from JWT token."""
        return self.subject_id(self.verify_token(token))

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify access token specifically."""
        payload = self.verify_token(token)

        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """Verify refresh token specifically."""
        payload = self.verify_token(token)

        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    def create_special_token(self, user_id: int, token_type: str, expires_minutes: int) -> str:
        """Create a short-lived, single-purpose token (reset, magic link, MFA step).

        ``token_type`` is anything but ``access``/``refresh`` so these tokens can
        never be presented as credentials to protected endpoints.
        """
        if token_type in {"access", "refresh"}:
            raise ValueError("use create_access_token / create_refresh_token")
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "exp": now + timedelta(minutes=expires_minutes),
            "iat": now,
            "type": token_type,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_special_token(self, token: str, token_type: str) -> dict[str, Any]:
        """Verify a token created by :meth:`create_special_token` of the given type."""
        payload = self.verify_token(token)
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    def create_password_reset_token(self, user_id: int, expires_minutes: int = 30) -> str:
        """Create a short-lived password reset token."""
        return self.create_special_token(user_id, "password_reset", expires_minutes)

    def create_token_pair(
        self, user_id: int, additional_data: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """Create both access and refresh tokens."""
        token_data = {"sub": str(user_id)}

        if additional_data:
            token_data.update(additional_data)

        access_token = self.create_access_token(data=token_data)
        refresh_token = self.create_refresh_token(data=token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }


# Global security manager instance
security_manager = SecurityManager()


# Utility functions for backward compatibility
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using global security manager."""
    return security_manager.verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using global security manager."""
    return security_manager.get_password_hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create access token using global security manager."""
    return security_manager.create_access_token(data, expires_delta)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create refresh token using global security manager."""
    return security_manager.create_refresh_token(data, expires_delta)


def verify_token(token: str) -> dict[str, Any]:
    """Verify token using global security manager."""
    return security_manager.verify_token(token)
