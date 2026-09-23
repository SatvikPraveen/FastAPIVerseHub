# File: app/services/token_service.py
"""Refresh-token lifecycle: issuance, rotation, reuse detection, revocation.

Access tokens stay stateless JWTs (with a Redis jti blacklist for logout).
Refresh tokens are *also* JWTs but every one is recorded in ``refresh_tokens``
so that:

* a refresh token can be used exactly once (rotation);
* presenting an already-rotated token is treated as theft and revokes the
  whole token *family* (every token descended from the original login);
* "log out everywhere" is a single UPDATE.

Only a SHA-256 of the token is stored; a database leak does not yield
usable credentials.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import security_manager
from app.core.time import from_timestamp, utcnow
from app.models.token import RefreshToken
from app.models.user import User

logger = get_logger(__name__)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


class TokenService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    async def issue_pair(
        self,
        user: User,
        *,
        extra_claims: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        family: str | None = None,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Create an access/refresh pair and record the refresh token."""
        claims = {"email": user.email, "is_superuser": user.is_superuser, **(extra_claims or {})}
        tokens: dict[str, Any] = dict(
            security_manager.create_token_pair(user_id=user.id, additional_data=claims)
        )

        payload = security_manager.verify_refresh_token(tokens["refresh_token"])
        record = RefreshToken(
            user_id=user.id,
            token_hash=self.hash_token(tokens["refresh_token"]),
            jti=str(payload["jti"]),
            ip_address=ip_address,
            user_agent=(user_agent or "")[:1000] or None,
            issued_at=from_timestamp(float(payload["iat"])),
            expires_at=from_timestamp(float(payload["exp"])),
            token_family=family or uuid.uuid4().hex,
            parent_token_id=parent_id,
        )
        self.db.add(record)
        await self.db.commit()

        tokens["expires_in"] = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return tokens

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    async def rotate(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Exchange a refresh token for a new pair, invalidating the old one.

        Raises 401 for unknown, expired, tampered or already-used tokens.
        Reuse of a rotated token revokes its entire family.
        """
        payload = security_manager.verify_refresh_token(refresh_token)  # signature + exp
        jti = str(payload.get("jti") or "")
        record = (
            await self.db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        ).scalar_one_or_none()

        if record is None or record.token_hash != self.hash_token(refresh_token):
            raise _unauthorized("Unknown refresh token")

        if record.is_revoked:
            revoked = await self.revoke_family(record.token_family)
            logger.warning(
                "refresh token reuse detected; family revoked",
                user_id=record.user_id,
                family=record.token_family,
                revoked=revoked,
                client_ip=ip_address,
            )
            raise _unauthorized("Refresh token reuse detected; session revoked")

        if record.is_expired:
            raise _unauthorized("Refresh token has expired")

        user = await self.db.get(User, record.user_id)
        if user is None or not user.is_active or user.deleted_at is not None:
            raise _unauthorized("User is not active")

        record.revoke()
        record.last_used_at = utcnow()
        await self.db.flush()

        extra = {
            k: v
            for k, v in payload.items()
            if k in {"mfa_verified", "social_provider", "passwordless"}
        }
        return await self.issue_pair(
            user,
            extra_claims=extra,
            ip_address=ip_address,
            user_agent=user_agent,
            family=record.token_family,
            parent_id=record.id,
        )

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    async def revoke_refresh_token(self, refresh_token: str, user_id: int) -> bool:
        """Revoke one refresh token owned by ``user_id``. Never raises."""
        try:
            payload = security_manager.verify_refresh_token(refresh_token)
        except HTTPException:
            return False
        result = await self.db.execute(
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.jti == str(payload.get("jti") or ""),
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked.is_(False),
                )
            )
            .values(is_revoked=True, revoked_at=utcnow(), revoked_by=user_id)
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0) > 0

    async def revoke_family(self, family: str | None) -> int:
        if not family:
            return 0
        result = await self.db.execute(
            update(RefreshToken)
            .where(and_(RefreshToken.token_family == family, RefreshToken.is_revoked.is_(False)))
            .values(is_revoked=True, revoked_at=utcnow())
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Log the user out everywhere: every live refresh token is revoked."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(and_(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False)))
            .values(is_revoked=True, revoked_at=utcnow(), revoked_by=user_id)
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def active_session_count(self, user_id: int) -> int:
        return int(
            (
                await self.db.execute(
                    select(func.count(RefreshToken.id)).where(
                        and_(
                            RefreshToken.user_id == user_id,
                            RefreshToken.is_revoked.is_(False),
                            RefreshToken.expires_at > utcnow(),
                        )
                    )
                )
            ).scalar()
            or 0
        )
