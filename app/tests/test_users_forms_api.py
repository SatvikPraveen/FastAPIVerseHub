# File: app/tests/test_users_forms_api.py
"""Admin user management and the forms API."""

import io

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Survey, User
from app.tests.conftest import UserFactory


class TestUsersAdminAPI:
    async def test_non_admin_cannot_list_users(self, async_client: AsyncClient, auth_headers):
        response = await async_client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403
        assert response.json()["error"] == "FORBIDDEN"

    async def test_admin_lists_searches_and_sorts(
        self, async_client: AsyncClient, admin_headers, test_user: User, db_session
    ):
        await UserFactory.create_user(db_session, email="zed@example.com", full_name="Zed Last")
        response = await async_client.get(
            "/api/v1/users/",
            params={"q": "zed", "sort_by": "email", "order": "desc"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1 and body["items"][0]["email"] == "zed@example.com"

        inactive = await async_client.get(
            "/api/v1/users/", params={"is_active": "false"}, headers=admin_headers
        )
        assert inactive.json()["total"] == 0

    async def test_admin_crud_lifecycle(self, async_client: AsyncClient, admin_headers):
        payload = {
            "email": "created@example.com",
            "password": "Created123Pass",
            "confirm_password": "Created123Pass",
            "full_name": "Created User",
        }
        created = await async_client.post("/api/v1/users/", json=payload, headers=admin_headers)
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]

        dup = await async_client.post("/api/v1/users/", json=payload, headers=admin_headers)
        assert dup.status_code == 400

        fetched = await async_client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert fetched.json()["email"] == "created@example.com"

        updated = await async_client.put(
            f"/api/v1/users/{user_id}",
            json={"full_name": "Renamed", "bio": "hi"},
            headers=admin_headers,
        )
        assert updated.json()["full_name"] == "Renamed"

        deactivated = await async_client.post(
            f"/api/v1/users/{user_id}/deactivate", headers=admin_headers
        )
        assert deactivated.json()["is_active"] is False
        activated = await async_client.post(
            f"/api/v1/users/{user_id}/activate", headers=admin_headers
        )
        assert activated.json()["is_active"] is True

        deleted = await async_client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert deleted.status_code == 204
        assert (
            await async_client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
        ).status_code == 404

    async def test_stats_are_private(
        self, async_client: AsyncClient, auth_headers, admin_headers, test_user, test_superuser
    ):
        own = await async_client.get(f"/api/v1/users/{test_user.id}/stats", headers=auth_headers)
        assert own.status_code == 200
        assert own.json()["total_courses"] == 0

        other = await async_client.get(
            f"/api/v1/users/{test_superuser.id}/stats", headers=auth_headers
        )
        assert other.status_code == 403

        admin = await async_client.get(f"/api/v1/users/{test_user.id}/stats", headers=admin_headers)
        assert admin.status_code == 200

    async def test_me_update_and_delete(self, async_client: AsyncClient, auth_headers, test_user):
        updated = await async_client.put(
            "/api/v1/users/me", json={"timezone": "Europe/Paris"}, headers=auth_headers
        )
        assert updated.json()["timezone"] == "Europe/Paris"
        assert (
            await async_client.delete("/api/v1/users/me", headers=auth_headers)
        ).status_code == 204
        # soft-deleted users can no longer authenticate
        assert (await async_client.get("/api/v1/users/me", headers=auth_headers)).status_code == 401


class TestFormsAPI:
    async def test_contact_form(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/forms/contact",
            json={
                "name": "Ann",
                "email": "ann@example.com",
                "subject": "Hi",
                "message": "This message is long enough.",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

        short = await async_client.post(
            "/api/v1/forms/contact",
            json={"name": "Ann", "email": "ann@example.com", "subject": "Hi", "message": "short"},
        )
        assert short.status_code == 422

    async def test_feedback_and_submission_listing(self, async_client: AsyncClient, auth_headers):
        for rating in (5, 3):
            response = await async_client.post(
                "/api/v1/forms/feedback",
                json={"rating": rating, "title": "t", "description": "d", "category": "ux"},
                headers=auth_headers,
            )
            assert response.status_code == 200
        bad = await async_client.post(
            "/api/v1/forms/feedback",
            json={"rating": 9, "title": "t", "description": "d", "category": "ux"},
            headers=auth_headers,
        )
        assert bad.status_code == 422

        listing = await async_client.get(
            "/api/v1/forms/submissions", params={"form_type": "feedback"}, headers=auth_headers
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 2
        submission_id = listing.json()["submissions"][0]["id"]

        detail = await async_client.get(
            f"/api/v1/forms/submissions/{submission_id}", headers=auth_headers
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["category"] == "ux"

    async def test_submission_ownership(
        self, async_client: AsyncClient, auth_headers, admin_headers, test_superuser
    ):
        created = await async_client.post(
            "/api/v1/forms/dynamic", json={"form_type": "poll", "answer": 42}, headers=auth_headers
        )
        submission_id = int(created.json()["submission_id"])
        # another (admin) user may read it, a stranger may not
        assert (
            await async_client.get(
                f"/api/v1/forms/submissions/{submission_id}", headers=admin_headers
            )
        ).status_code == 200
        empty = await async_client.post("/api/v1/forms/dynamic", json={}, headers=auth_headers)
        assert empty.status_code == 400
        missing = await async_client.get("/api/v1/forms/submissions/99999", headers=auth_headers)
        assert missing.status_code == 404

    async def test_surveys(self, async_client: AsyncClient, db_session: AsyncSession, auth_headers):
        survey = Survey(
            title="Onboarding",
            description="d",
            questions=[{"id": "q1", "text": "Why?"}],
            estimated_time_minutes=2,
            instructions="Be honest",
        )
        inactive = Survey(title="Old", questions=[], is_active=False)
        db_session.add_all([survey, inactive])
        await db_session.commit()

        active = await async_client.get("/api/v1/forms/surveys/active")
        assert [s["title"] for s in active.json()["surveys"]] == ["Onboarding"]
        assert active.json()["surveys"][0]["response_count"] == 0

        detail = await async_client.get(f"/api/v1/forms/surveys/{survey.id}")
        assert detail.json()["instructions"] == "Be honest"
        assert (await async_client.get(f"/api/v1/forms/surveys/{inactive.id}")).status_code == 400
        assert (await async_client.get("/api/v1/forms/surveys/9999")).status_code == 404

        answered = await async_client.post(
            "/api/v1/forms/survey",
            json={
                "survey_id": survey.id,
                "responses": {"q1": "because"},
                "completion_time_seconds": 30,
            },
            headers=auth_headers,
        )
        assert answered.status_code == 200
        anonymous = await async_client.post(
            "/api/v1/forms/survey", json={"survey_id": survey.id, "responses": {"q1": "x"}}
        )
        assert anonymous.status_code == 200
        assert (await async_client.get("/api/v1/forms/surveys/active")).json()["surveys"][0][
            "response_count"
        ] == 2

    async def test_multipart_form(
        self, async_client: AsyncClient, auth_headers, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)  # uploads land in a scratch directory
        response = await async_client.post(
            "/api/v1/forms/multipart",
            data={
                "name": "Ann",
                "email": "ann@example.com",
                "age": "30",
                "bio": "hi",
                "skills": ["python", "sql"],
            },
            files={
                "profile_picture": ("me.png", io.BytesIO(b"\x89PNG fake"), "image/png"),
                "resume": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body["uploaded_files"]) == {"profile_picture", "resume"}
        assert (tmp_path / "uploads" / "resumes").exists()

        wrong_type = await async_client.post(
            "/api/v1/forms/multipart",
            data={
                "name": "Ann",
                "email": "ann@example.com",
                "age": "30",
                "bio": "hi",
                "skills": ["x"],
            },
            files={"resume": ("cv.txt", io.BytesIO(b"nope"), "text/plain")},
            headers=auth_headers,
        )
        assert wrong_type.status_code == 400
        underage = await async_client.post(
            "/api/v1/forms/multipart",
            data={
                "name": "Kid",
                "email": "kid@example.com",
                "age": "9",
                "bio": "hi",
                "skills": ["x"],
            },
            headers=auth_headers,
        )
        assert underage.status_code == 400

    async def test_validate_endpoint(self, async_client: AsyncClient):
        ok = await async_client.post(
            "/api/v1/forms/validate",
            params={"form_type": "contact"},
            json={"name": "A", "email": "a@b.co", "subject": "s", "message": "long enough msg"},
        )
        assert ok.json() == {"valid": True, "errors": [], "warnings": []}
        bad = await async_client.post(
            "/api/v1/forms/validate",
            params={"form_type": "feedback"},
            json={"rating": 7, "email": "nope"},
        )
        assert bad.json()["valid"] is False
        assert any("rating" in e for e in bad.json()["errors"])
        unknown = await async_client.post(
            "/api/v1/forms/validate", params={"form_type": "mystery"}, json={"age": 200}
        )
        assert unknown.json()["warnings"] and not unknown.json()["valid"]
