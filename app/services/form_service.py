# File: app/services/form_service.py
"""Form submissions, surveys and the multipart upload helper."""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

import aiofiles
from fastapi import UploadFile
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.user import FormSubmission, Survey

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormService:
    """Service for handling form submissions and surveys."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _persist(self, submission: FormSubmission) -> FormSubmission:
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    # ------------------------------------------------------------------
    # Contact / Feedback forms
    # ------------------------------------------------------------------

    async def save_contact_form(
        self,
        name: str,
        email: str,
        subject: str,
        message: str,
        phone: str | None = None,
    ) -> FormSubmission:
        """Persist a contact-form submission."""
        return await self._persist(
            FormSubmission(
                form_type="contact",
                data={
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                    "phone": phone,
                },
                submitter_name=name,
                submitter_email=email,
                is_anonymous=False,
                status="pending",
            )
        )

    async def save_feedback_form(
        self,
        user_id: int | None,
        rating: int,
        title: str,
        description: str,
        category: str,
        is_anonymous: bool = False,
    ) -> FormSubmission:
        """Persist a feedback-form submission."""
        return await self._persist(
            FormSubmission(
                user_id=None if is_anonymous else user_id,
                form_type="feedback",
                data={
                    "rating": rating,
                    "title": title,
                    "description": description,
                    "category": category,
                },
                is_anonymous=is_anonymous,
                status="received",
            )
        )

    async def save_multipart_form(
        self,
        user_id: int,
        name: str,
        email: str,
        age: int,
        bio: str,
        skills: list[str],
        uploaded_files: dict[str, dict[str, Any]],
    ) -> FormSubmission:
        """Persist a multipart form together with metadata of its uploaded files."""
        return await self._persist(
            FormSubmission(
                user_id=user_id,
                form_type="multipart",
                data={
                    "name": name,
                    "email": email,
                    "age": age,
                    "bio": bio,
                    "skills": skills,
                    "files": uploaded_files,
                },
                submitter_name=name,
                submitter_email=email,
                status="received",
            )
        )

    async def save_dynamic_form(
        self, user_id: int | None, form_type: str, form_data: dict[str, Any]
    ) -> FormSubmission:
        """Persist an arbitrary JSON form payload."""
        return await self._persist(
            FormSubmission(
                user_id=user_id,
                form_type=form_type,
                data=form_data,
                is_anonymous=user_id is None,
                status="received",
            )
        )

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    async def get_submission_by_id(self, submission_id: int) -> FormSubmission | None:
        return await self.db.get(FormSubmission, submission_id)

    async def get_user_submissions(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        form_type: str | None = None,
    ) -> tuple[list[FormSubmission], int]:
        """Paginated submissions for one user, newest first."""
        criteria = [FormSubmission.user_id == user_id]
        if form_type:
            criteria.append(FormSubmission.form_type == form_type)
        where = and_(*criteria)

        total = (await self.db.execute(select(func.count(FormSubmission.id)).where(where))).scalar()
        rows = await self.db.execute(
            select(FormSubmission)
            .where(where)
            .order_by(FormSubmission.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def mark_processed(self, submission_id: int, status: str = "resolved") -> bool:
        submission = await self.get_submission_by_id(submission_id)
        if not submission:
            return False
        submission.status = status
        submission.processed_at = utcnow()
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Surveys
    # ------------------------------------------------------------------

    async def get_survey_by_id(self, survey_id: int) -> Survey | None:
        return await self.db.get(Survey, survey_id)

    async def get_active_surveys(self) -> list[dict[str, Any]]:
        """Active surveys with their response counts, in one query."""
        responses = (
            select(FormSubmission.survey_id, func.count(FormSubmission.id).label("n"))
            .where(FormSubmission.form_type == "survey")
            .group_by(FormSubmission.survey_id)
            .subquery()
        )
        rows = await self.db.execute(
            select(Survey, func.coalesce(responses.c.n, 0))
            .outerjoin(responses, responses.c.survey_id == Survey.id)
            .where(Survey.is_active.is_(True))
            .order_by(Survey.created_at.desc())
        )
        return [
            {
                "id": survey.id,
                "title": survey.title,
                "description": survey.description,
                "estimated_time_minutes": survey.estimated_time_minutes,
                "total_questions": len(survey.questions or []),
                "response_count": int(count),
            }
            for survey, count in rows.all()
        ]

    async def save_survey_response(
        self,
        survey_id: int,
        user_id: int | None,
        responses: dict[str, Any],
        completion_time_seconds: int | None = None,
    ) -> FormSubmission:
        """Persist a survey response submission."""
        return await self._persist(
            FormSubmission(
                user_id=user_id,
                form_type="survey",
                data=responses,
                survey_id=survey_id,
                completion_time_seconds=completion_time_seconds,
                is_anonymous=user_id is None,
                status="completed",
            )
        )

    # ------------------------------------------------------------------
    # Validation (no database needed)
    # ------------------------------------------------------------------

    _REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
        "contact": ("name", "email", "subject", "message"),
        "feedback": ("rating", "title", "description", "category"),
        "survey": ("survey_id", "responses"),
        "multipart": ("name", "email", "age", "bio"),
    }

    @classmethod
    def validate_form_data(cls, form_type: str, form_data: dict[str, Any]) -> dict[str, Any]:
        """Dry-run validation used by ``POST /forms/validate``.

        Returns ``{"valid": bool, "errors": [...], "warnings": [...]}``.
        """
        errors: list[str] = []
        warnings: list[str] = []

        required = cls._REQUIRED_FIELDS.get(form_type)
        if required is None:
            warnings.append(f"Unknown form type '{form_type}'; only generic checks applied")
            required = ()

        for name in required:
            value = form_data.get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"'{name}' is required")

        email = form_data.get("email")
        if isinstance(email, str) and email and not _EMAIL_RE.match(email):
            errors.append("'email' is not a valid email address")

        rating = form_data.get("rating")
        if rating is not None and not (isinstance(rating, int) and 1 <= rating <= 5):
            errors.append("'rating' must be an integer between 1 and 5")

        message = form_data.get("message")
        if isinstance(message, str) and 0 < len(message.strip()) < 10:
            errors.append("'message' must be at least 10 characters")

        age = form_data.get("age")
        if age is not None and not (isinstance(age, int) and 13 <= age <= 120):
            errors.append("'age' must be between 13 and 120")

        return {"valid": not errors, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # File upload helper (used by multipart form endpoint)
    # ------------------------------------------------------------------

    async def save_uploaded_file(
        self, upload: UploadFile, user_id: int, sub_dir: str = "misc"
    ) -> dict[str, Any]:
        """Write an uploaded file to disk and return metadata."""
        upload_root = os.path.join("uploads", sub_dir, str(user_id))
        os.makedirs(upload_root, exist_ok=True)

        ext = os.path.splitext(upload.filename or "")[1]
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_root, stored_name)

        content = await upload.read()
        async with aiofiles.open(file_path, "wb") as fh:
            await fh.write(content)

        return {
            "filename": stored_name,
            "original_filename": upload.filename,
            "stored_filename": stored_name,
            "file_path": file_path,
            "file_size": len(content),
            "content_type": upload.content_type,
            "download_url": f"/uploads/{sub_dir}/{user_id}/{stored_name}",
        }
