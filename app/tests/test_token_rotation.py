# File: app/tests/test_token_rotation.py
"""Refresh-token rotation, reuse detection and revocation."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken
from app.models.user import User

LOGIN = {"email": "test@example.com", "password": "testpassword123"}


async def _login(client: AsyncClient) -> dict:
    response = await client.post("/api/v1/auth/login", json=LOGIN)
    assert response.status_code == 200, response.text
    return response.json()


async def test_login_records_refresh_token(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession
):
    tokens = await _login(async_client)
    assert tokens["expires_in"] > 0

    rows = (await db_session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 1
    record = rows[0]
    assert record.user_id == test_user.id
    assert record.token_family and record.parent_token_id is None
    assert record.token_hash != tokens["refresh_token"]  # only a hash is stored
    assert record.is_revoked is False


async def test_refresh_rotates_token(async_client: AsyncClient, test_user: User, db_session):
    first = await _login(async_client)

    response = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert response.status_code == 200, response.text
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert second["access_token"] != first["access_token"]

    rows = (
        (await db_session.execute(select(RefreshToken).order_by(RefreshToken.id))).scalars().all()
    )
    assert len(rows) == 2
    old, new = rows
    assert old.is_revoked is True and old.last_used_at is not None
    assert new.is_revoked is False
    assert new.token_family == old.token_family
    assert new.parent_token_id == old.id


async def test_reusing_rotated_token_revokes_family(async_client: AsyncClient, test_user: User):
    first = await _login(async_client)
    second = (
        await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
        )
    ).json()

    # An attacker (or a buggy client) replays the already-rotated token...
    replay = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    assert "reuse" in replay.json()["message"].lower()

    # ...which burns the legitimate descendant too.
    legit = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert legit.status_code == 401


async def test_unknown_or_forged_refresh_token_rejected(async_client: AsyncClient, test_user):
    from app.core.security import security_manager

    forged = security_manager.create_refresh_token(data={"sub": str(test_user.id)})
    response = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": forged})
    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"

    response = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert response.status_code == 401


async def test_access_token_cannot_be_used_as_refresh(async_client: AsyncClient, test_user):
    tokens = await _login(async_client)
    response = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


async def test_logout_with_refresh_token_ends_session(async_client: AsyncClient, test_user):
    tokens = await _login(async_client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await async_client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["refresh_token_revoked"] is True

    # the blacklisted access token no longer works...
    assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    # ...and neither does the refresh token
    refreshed = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401


async def test_logout_everywhere_revokes_every_device(async_client: AsyncClient, test_user):
    phone = await _login(async_client)
    laptop = await _login(async_client)
    headers = {"Authorization": f"Bearer {laptop['access_token']}"}

    response = await async_client.post("/api/v1/auth/logout-all", headers=headers)
    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 2

    for tokens in (phone, laptop):
        refreshed = await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 401


async def test_inactive_user_cannot_refresh(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession
):
    tokens = await _login(async_client)
    test_user.is_active = False
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


async def test_registration_sends_welcome_email_after_response(
    async_client: AsyncClient, sample_user_data
):
    with patch("app.api.v1.auth.EmailService.send_welcome_email", new_callable=AsyncMock) as send:
        response = await async_client.post("/api/v1/auth/register", json=sample_user_data)

    assert response.status_code == 201
    send.assert_awaited_once_with(sample_user_data["email"], sample_user_data["full_name"])


async def test_forgot_password_sends_reset_email_only_for_known_users(
    async_client: AsyncClient, test_user: User
):
    with patch(
        "app.api.v1.auth.EmailService.send_password_reset_email", new_callable=AsyncMock
    ) as send:
        known = await async_client.post(
            "/api/v1/auth/forgot-password", json={"email": test_user.email}
        )
        unknown = await async_client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
        )

    # identical responses: the endpoint never reveals whether an address exists
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    send.assert_awaited_once()
    assert send.await_args.args[0] == test_user.email
