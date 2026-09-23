# File: app/tests/test_v2_auth.py
"""MFA, devices, sessions, passwordless and social login (v2 auth)."""

from unittest.mock import AsyncMock, patch

import pyotp
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import security_manager
from app.models.user import User
from app.services.auth_service import AuthService

PASSWORD = "testpassword123"


class TestMFA:
    async def _enable(self, client: AsyncClient, headers) -> str:
        setup = await client.post(
            "/api/v2/auth/mfa/setup", json={"password": PASSWORD}, headers=headers
        )
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        assert setup.json()["qr_code"].startswith("data:image/png;base64,")
        assert len(setup.json()["backup_codes"]) == 10

        verify = await client.post(
            "/api/v2/auth/mfa/verify", json={"token": pyotp.TOTP(secret).now()}, headers=headers
        )
        assert verify.status_code == 200, verify.text
        return secret

    async def test_setup_requires_password(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/v2/auth/mfa/setup", json={"password": "wrong"}, headers=auth_headers
        )
        assert response.status_code == 400

    async def test_full_lifecycle(self, async_client, auth_headers, test_user: User, db_session):
        secret = await self._enable(async_client, auth_headers)
        await db_session.refresh(test_user)
        assert test_user.mfa_enabled

        # already enabled -> setup refused; wrong code -> verify refused
        assert (
            await async_client.post(
                "/api/v2/auth/mfa/setup", json={"password": PASSWORD}, headers=auth_headers
            )
        ).status_code == 400
        assert (
            await async_client.post(
                "/api/v2/auth/mfa/verify", json={"token": "000000"}, headers=auth_headers
            )
        ).status_code == 400

        # password-only login now returns an MFA challenge, never an access token
        challenge = await async_client.post(
            "/api/v2/auth/login/mfa", params={"email": test_user.email, "password": PASSWORD}
        )
        assert challenge.status_code == 200, challenge.text
        body = challenge.json()
        assert body["requires_mfa"] is True and body["access_token"] is None
        partial = {"Authorization": f"Bearer {body['partial_token']}"}
        assert (await async_client.get("/api/v1/auth/me", headers=partial)).status_code == 401

        # with a valid code we get real tokens
        ok = await async_client.post(
            "/api/v2/auth/login/mfa",
            params={
                "email": test_user.email,
                "password": PASSWORD,
                "mfa_token": pyotp.TOTP(secret).now(),
            },
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["access_token"] and ok.json()["user"]["mfa_enabled"] is True
        bad = await async_client.post(
            "/api/v2/auth/login/mfa",
            params={"email": test_user.email, "password": PASSWORD, "mfa_token": "111111"},
        )
        assert bad.status_code == 401
        wrong_pw = await async_client.post(
            "/api/v2/auth/login/mfa", params={"email": test_user.email, "password": "nope"}
        )
        assert wrong_pw.status_code == 401

        # backup codes work once
        await db_session.refresh(test_user)
        code = test_user.backup_codes[0]
        via_backup = await async_client.post(
            "/api/v2/auth/login/mfa",
            params={"email": test_user.email, "password": PASSWORD, "backup_code": code},
        )
        assert via_backup.status_code == 200
        reused = await async_client.post(
            "/api/v2/auth/login/mfa",
            params={"email": test_user.email, "password": PASSWORD, "backup_code": code},
        )
        assert reused.status_code == 401

        disabled = await async_client.post(
            "/api/v2/auth/mfa/disable",
            json={"token": pyotp.TOTP(secret).now()},
            headers=auth_headers,
        )
        assert disabled.status_code == 200
        assert (
            await async_client.post(
                "/api/v2/auth/mfa/disable", json={"token": "1"}, headers=auth_headers
            )
        ).status_code == 400


class TestDevicesAndSessions:
    async def test_devices(self, async_client, auth_headers):
        registered = await async_client.post(
            "/api/v2/auth/devices/register",
            json={"device_name": "Phone", "device_type": "mobile", "device_fingerprint": "fp"},
            headers=auth_headers,
        )
        assert registered.status_code == 200, registered.text
        device_id = registered.json()["device_id"]
        listed = await async_client.get("/api/v2/auth/devices", headers=auth_headers)
        assert [d["id"] for d in listed.json()["devices"]] == [device_id]
        revoked = await async_client.delete(
            f"/api/v2/auth/devices/{device_id}", headers=auth_headers
        )
        assert revoked.status_code == 200
        assert (await async_client.get("/api/v2/auth/devices", headers=auth_headers)).json()[
            "devices"
        ] == []

    async def test_sessions(self, async_client, auth_headers, test_user, db_session):
        await AuthService(db_session).create_user_session(test_user.id, "s1", ip_address="9.9.9.9")
        await AuthService(db_session).create_user_session(test_user.id, "s2")
        listed = await async_client.get("/api/v2/auth/sessions", headers=auth_headers)
        assert {s["session_id"] for s in listed.json()["sessions"]} == {"s1", "s2"}
        assert (
            await async_client.delete("/api/v2/auth/sessions/s1", headers=auth_headers)
        ).status_code == 200
        assert (
            len(
                (await async_client.get("/api/v2/auth/sessions", headers=auth_headers)).json()[
                    "sessions"
                ]
            )
            == 1
        )
        revoked_all = await async_client.post(
            "/api/v2/auth/sessions/revoke-all", headers=auth_headers
        )
        assert "Revoked" in revoked_all.json()["message"]


class TestPasswordless:
    async def test_request_and_verify(self, async_client, test_user: User):
        with patch.object(AuthService, "send_magic_link_email", new_callable=AsyncMock) as send:
            requested = await async_client.post(
                "/api/v2/auth/passwordless/request", json={"email": test_user.email}
            )
            unknown = await async_client.post(
                "/api/v2/auth/passwordless/request", json={"email": "ghost@example.com"}
            )
        assert requested.status_code == unknown.status_code == 200
        send.assert_awaited_once()
        token = send.await_args.args[1]

        verified = await async_client.post(
            "/api/v2/auth/passwordless/verify", json={"token": token}
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["access_token"]

        # an ordinary access token is not a magic link
        access = security_manager.create_access_token(data={"sub": str(test_user.id)})
        rejected = await async_client.post(
            "/api/v2/auth/passwordless/verify", json={"token": access}
        )
        assert rejected.status_code == 400

    async def test_sms_requires_phone(self, async_client, test_user: User):
        response = await async_client.post(
            "/api/v2/auth/passwordless/request", json={"email": test_user.email, "method": "sms"}
        )
        assert response.status_code == 400


class TestSocialAuth:
    async def test_unconfigured_provider_refused(self, async_client, monkeypatch):
        monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", None)
        response = await async_client.post(
            "/api/v2/auth/social/auth", json={"provider": "github", "access_token": "tok"}
        )
        assert response.status_code == 400
        assert "not configured" in response.json()["message"]

    async def test_github_login_creates_user(self, async_client, monkeypatch, db_session):
        monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "gh-client")
        payloads = {
            "https://api.github.com/user": {
                "id": 77,
                "login": "octo",
                "name": None,
                "avatar_url": "a.png",
            },
            "https://api.github.com/user/emails": [
                {"email": "old@example.com", "primary": False, "verified": True},
                {"email": "Octo@Example.com", "primary": True, "verified": True},
            ],
        }

        async def fake_get_json(self, url, headers=None, params=None):
            assert headers["Authorization"] == "Bearer tok"
            return payloads.get(url)

        monkeypatch.setattr(AuthService, "_get_json", fake_get_json)
        response = await async_client.post(
            "/api/v2/auth/social/auth", json={"provider": "github", "access_token": "tok"}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user"]["email"] == "octo@example.com"
        assert body["user"]["is_new_user"] is True and body["access_token"]

    async def test_provider_rejects_token(self, async_client, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "g-client")

        async def fake_get_json(self, url, headers=None, params=None):
            return None

        monkeypatch.setattr(AuthService, "_get_json", fake_get_json)
        response = await async_client.post(
            "/api/v2/auth/social/auth", json={"provider": "google", "access_token": "bad"}
        )
        assert response.status_code == 401

    async def test_google_audience_and_verification_checked(self, monkeypatch, db_session):
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "g-client")
        service = AuthService(db_session)
        responses = [
            {"aud": "someone-else", "sub": "1", "email": "a@b.co", "email_verified": "true"}
        ]

        async def fake_get_json(self, url, headers=None, params=None):
            return responses.pop(0) if responses else None

        monkeypatch.setattr(AuthService, "_get_json", fake_get_json)
        assert await service.verify_social_token("google", "t", id_token="idt") is None

        responses.append(
            {"aud": "g-client", "sub": "1", "email": "A@b.co", "email_verified": "false"}
        )
        assert await service.verify_social_token("google", "t", id_token="idt") is None

        responses.append(
            {
                "aud": "g-client",
                "sub": "1",
                "email": "A@b.co",
                "email_verified": "true",
                "name": "A",
            }
        )
        identity = await service.verify_social_token("google", "t", id_token="idt")
        assert identity == {"id": "1", "email": "a@b.co", "name": "A", "picture": None}
        assert await service.verify_social_token("facebook", "t") is None

    async def test_network_failure_is_not_a_login(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "li")
        import httpx

        class Boom:
            def __init__(self, *a, **k): ...
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                raise httpx.ConnectError("down")

        monkeypatch.setattr(httpx, "AsyncClient", Boom)
        assert await AuthService(db_session).verify_social_token("linkedin", "t") is None
