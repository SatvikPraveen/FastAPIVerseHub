# File: app/api/v1/forms.py

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.services.form_service import FormService

router = APIRouter()


class ContactForm(BaseModel):
    """Contact form schema."""
    name: str
    email: EmailStr
    subject: str
    message: str
    phone: Optional[str] = None
    
    @validator('message')
    def validate_message(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Message must be at least 10 characters long')
        return v.strip()


class FeedbackForm(BaseModel):
    """Feedback form schema."""
    rating: int
    title: str
    description: str
    category: str
    anonymous: bool = False
    
    @validator('rating')
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Rating must be between 1 and 5')
        return v


class SurveyResponse(BaseModel):
    """Survey response schema."""
    survey_id: int
    responses: Dict[str, str]
    completion_time_seconds: Optional[int] = None


@router.post("/contact")
async def submit_contact_form(
    contact_form: ContactForm,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Submit contact form."""
    form_service = FormService(db)
    
    # Save contact form submission
    submission = await form_service.save_contact_form(
        name=contact_form.name,
        email=contact_form.email,
        subject=contact_form.subject,
        message=contact_form.message,
        phone=contact_form.phone
    )
    
    # TODO: Send email notification to admin
    # await email_service.send_contact_form_notification(contact_form)
    
    return {
        "message": "Contact form submitted successfully",
        "submission_id": str(submission.id),
        "status": "pending"
    }


@router.post("/feedback")
async def submit_feedback_form(
    feedback_form: FeedbackForm,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Submit feedback form."""
    form_service = FormService(db)
    
    submission = await form_service.save_feedback_form(
        user_id=current_user.id if not feedback_form.anonymous else None,
        rating=feedback_form.rating,
        title=feedback_form.title,
        description=feedback_form.description,
        category=feedback_form.category,
        is_anonymous=feedback_form.anonymous
    )
    
    return {
        "message": "Feedback submitted successfully",
        "submission_id": str(submission.id),
        "status": "received"
    }


@router.post("/survey")
async def submit_survey_response(
    survey_response: SurveyResponse,
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Submit survey response."""
    form_service = FormService(db)
    
    # Check if survey exists
    survey = await form_service.get_survey_by_id(survey_response.survey_id)
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    if not survey.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not active"
        )
    
    # Save survey response
    submission = await form_service.save_survey_response(
        survey_id=survey_response.survey_id,
        user_id=current_user.id if current_user else None,
        responses=survey_response.responses,
        completion_time_seconds=survey_response.completion_time_seconds
    )
    
    return {
        "message": "Survey response submitted successfully",
        "submission_id": str(submission.id),
        "survey_id": str(survey_response.survey_id)
    }


@router.post("/multipart")
async def submit_multipart_form(
    name: str = Form(...),
    email: EmailStr = Form(...),
    age: int = Form(...),
    bio: str = Form(...),
    profile_picture: Optional[UploadFile] = File(None),
    resume: Optional[UploadFile] = File(None),
    skills: List[str] = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Submit multipart form with file uploads."""
    form_service = FormService(db)
    
    # Validate age
    if not 13 <= age <= 120:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Age must be between 13 and 120"
        )
    
    # Validate files if provided
    uploaded_files = {}
    
    if profile_picture:
        if not profile_picture.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile picture must be an image"
            )
        if profile_picture.size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile picture must be under 5MB"
            )
        
        # Save profile picture
        saved_file = await form_service.save_uploaded_file(
            profile_picture, 
            current_user.id, 
            "profile_pictures"
        )
        uploaded_files["profile_picture"] = saved_file
    
    if resume:
        if not resume.content_type == 'application/pdf':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume must be a PDF file"
            )
        if resume.size > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume must be under 10MB"
            )
        
        # Save resume
        saved_file = await form_service.save_uploaded_file(
            resume, 
            current_user.id, 
            "resumes"
        )
        uploaded_files["resume"] = saved_file
    
    # Save form submission
    submission = await form_service.save_multipart_form(
        user_id=current_user.id,
        name=name,
        email=email,
        age=age,
        bio=bio,
        skills=skills,
        uploaded_files=uploaded_files
    )
    
    return {
        "message": "Multipart form submitted successfully",
        "submission_id": str(submission.id),
        "uploaded_files": {
            key: {
                "filename": file_info["filename"],
                "file_size": file_info["file_size"],
                "download_url": file_info["download_url"]
            }
            for key, file_info in uploaded_files.items()
        }
    }


@router.post("/dynamic")
async def submit_dynamic_form(
    form_data: Dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Submit dynamic form with flexible schema."""
    form_service = FormService(db)
    
    # Basic validation
    if not form_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form data cannot be empty"
        )
    
    # Get form type if specified
    form_type = form_data.get("form_type", "general")
    
    # Save dynamic form submission
    submission = await form_service.save_dynamic_form(
        user_id=current_user.id,
        form_type=form_type,
        form_data=form_data
    )
    
    return {
        "message": "Dynamic form submitted successfully",
        "submission_id": str(submission.id),
        "form_type": form_type
    }


@router.get("/submissions")
async def get_user_submissions(
    skip: int = 0,
    limit: int = 20,
    form_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get user's form submissions."""
    form_service = FormService(db)
    
    submissions, total = await form_service.get_user_submissions(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        form_type=form_type
    )
    
    return {
        "submissions": [
            {
                "id": sub.id,
                "form_type": sub.form_type,
                "status": sub.status,
                "created_at": sub.created_at,
                "updated_at": sub.updated_at
            }
            for sub in submissions
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/submissions/{submission_id}")
async def get_submission_details(
    submission_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get detailed form submission."""
    form_service = FormService(db)
    
    submission = await form_service.get_submission_by_id(submission_id)
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Check ownership
    if submission.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return {
        "id": submission.id,
        "form_type": submission.form_type,
        "status": submission.status,
        "data": submission.form_data,
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
        "processed_at": submission.processed_at
    }


@router.get("/surveys/active")
async def get_active_surveys(
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get list of active surveys."""
    form_service = FormService(db)
    
    surveys = await form_service.get_active_surveys()
    
    return {
        "surveys": [
            {
                "id": survey.id,
                "title": survey.title,
                "description": survey.description,
                "estimated_time_minutes": survey.estimated_time_minutes,
                "total_questions": len(survey.questions),
                "response_count": survey.response_count
            }
            for survey in surveys
        ]
    }


@router.get("/surveys/{survey_id}")
async def get_survey_details(
    survey_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get survey details and questions."""
    form_service = FormService(db)
    
    survey = await form_service.get_survey_by_id(survey_id)
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    if not survey.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not active"
        )
    
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "estimated_time_minutes": survey.estimated_time_minutes,
        "questions": survey.questions,
        "instructions": survey.instructions,
        "created_at": survey.created_at
    }


@router.post("/validate")
async def validate_form_data(
    form_type: str,
    form_data: Dict
) -> Dict[str, bool]:
    """Validate form data without submitting."""
    form_service = FormService()
    
    # Perform validation based on form type
    validation_result = await form_service.validate_form_data(form_type, form_data)
    
    return {
        "valid": validation_result["valid"],
        "errors": validation_result.get("errors", []),
        "warnings": validation_result.get("warnings", [])
    }