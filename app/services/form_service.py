# File: app/services/form_service.py

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import FormSubmission, Survey


class FormService:
    """Service for handling form submissions and surveys."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Contact / Feedback forms
    # ------------------------------------------------------------------

    async def save_contact_form(
        self,
        name: str,
        email: str,
        subject: str,
        message: str,
        phone: Optional[str] = None,
    ) -> FormSubmission:
        """Persist a contact-form submission."""
        data = {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "phone": phone,
        }
        submission = FormSubmission(
            form_type="contact",
            data=data,
            submitter_name=name,
            submitter_email=email,
            is_anonymous=False,
            status="pending",
        )
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def save_feedback_form(
        self,
        user_id: Optional[int],
        rating: int,
        title: str,
        description: str,
        category: str,
        is_anonymous: bool = False,
    ) -> FormSubmission:
        """Persist a feedback-form submission."""
        data = {
            "rating": rating,
            "title": title,
            "description": description,
            "category": category,
        }
        submission = FormSubmission(
            user_id=user_id if not is_anonymous else None,
            form_type="feedback",
            data=data,
            is_anonymous=is_anonymous,
            status="received",
        )
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    # ------------------------------------------------------------------
    # Survey
    # ------------------------------------------------------------------

    async def get_survey_by_id(self, survey_id: int) -> Optional[Survey]:
        """Retrieve a survey by its primary key."""
        query = select(Survey).where(Survey.id == survey_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_survey_response(
        self,
        survey_id: int,
        user_id: Optional[int],
        responses: Dict[str, Any],
        completion_time_seconds: Optional[int] = None,
    ) -> FormSubmission:
        """Persist a survey response submission."""
        submission = FormSubmission(
            user_id=user_id,
            form_type="survey",
            data=responses,
            survey_id=survey_id,
            completion_time_seconds=completion_time_seconds,
            status="completed",
        )
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    # ------------------------------------------------------------------
    # File upload helper (used by multipart form endpoint)
    # ------------------------------------------------------------------

    async def save_uploaded_file(
        self, upload: UploadFile, user_id: int, sub_dir: str = "misc"
    ) -> Dict[str, Any]:
        """Write an uploaded file to disk and return metadata."""
        upload_root = os.path.join("uploads", sub_dir, str(user_id))
        os.makedirs(upload_root, exist_ok=True)

        ext = os.path.splitext(upload.filename or "")[1]
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_root, stored_name)

        content = await upload.read()
        with open(file_path, "wb") as fh:
            fh.write(content)

        return {
            "original_filename": upload.filename,
            "stored_filename": stored_name,
            "file_path": file_path,
            "file_size": len(content),
            "content_type": upload.content_type,
        }
