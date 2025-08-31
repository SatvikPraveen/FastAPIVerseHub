# File: app/api/v1/courses.py

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    get_current_user_optional,
    get_db,
    get_pagination_params,
    get_search_params,
    PaginationParams,
    SearchParams
)
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    CourseWithStats
)
from app.services.course_service import CourseService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[CourseResponse])
async def list_courses(
    pagination: PaginationParams = Depends(get_pagination_params),
    search: SearchParams = Depends(get_search_params),
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    is_published: Optional[bool] = Query(None, description="Filter by published status"),
    current_user: Optional[User] = Depends(get_current_user_optional()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """List all courses with optional filters."""
    course_service = CourseService(db)
    
    courses, total = await course_service.get_courses(
        skip=pagination.skip,
        limit=pagination.limit,
        search_query=search.query,
        category_filter=category,
        difficulty_filter=difficulty,
        is_published_filter=is_published,
        user_id=current_user.id if current_user else None,
        sort_by=search.sort_by,
        order=search.order
    )
    
    return {
        "items": [CourseResponse.from_orm(course) for course in courses],
        "total": total,
        "skip": pagination.skip,
        "limit": pagination.limit,
        "has_next": (pagination.skip + pagination.limit) < total
    }


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_create: CourseCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> CourseResponse:
    """Create a new course."""
    course_service = CourseService(db)
    
    course = await course_service.create_course(
        course_create=course_create,
        instructor_id=current_user.id
    )
    
    return CourseResponse.from_orm(course)


@router.get("/{course_id}", response_model=CourseWithStats)
async def get_course(
    course_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional()),
    db: AsyncSession = Depends(get_db)
) -> CourseWithStats:
    """Get course by ID with statistics."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if user can access unpublished course
    if not course.is_published:
        if not current_user or (
            current_user.id != course.instructor_id and not current_user.is_superuser
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
    
    # Get course statistics
    stats = await course_service.get_course_stats(course_id)
    
    course_data = CourseResponse.from_orm(course).dict()
    course_data.update({
        "total_enrollments": stats.get("total_enrollments", 0),
        "completed_enrollments": stats.get("completed_enrollments", 0),
        "average_rating": stats.get("average_rating", 0.0),
        "total_reviews": stats.get("total_reviews", 0)
    })
    
    return CourseWithStats(**course_data)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course_update: CourseUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> CourseResponse:
    """Update course by ID."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.id != course.instructor_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this course"
        )
    
    updated_course = await course_service.update_course(
        course_id=course_id,
        course_update=course_update
    )
    
    return CourseResponse.from_orm(updated_course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete course by ID."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.id != course.instructor_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this course"
        )
    
    await course_service.delete_course(course_id)


@router.post("/{course_id}/publish", response_model=CourseResponse)
async def publish_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> CourseResponse:
    """Publish a course."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.id != course.instructor_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to publish this course"
        )
    
    if course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course is already published"
        )
    
    published_course = await course_service.publish_course(course_id)
    return CourseResponse.from_orm(published_course)


@router.post("/{course_id}/unpublish", response_model=CourseResponse)
async def unpublish_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> CourseResponse:
    """Unpublish a course."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.id != course.instructor_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to unpublish this course"
        )
    
    if not course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course is already unpublished"
        )
    
    unpublished_course = await course_service.unpublish_course(course_id)
    return CourseResponse.from_orm(unpublished_course)


@router.post("/{course_id}/enroll")
async def enroll_in_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Enroll user in a course."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    if not course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll in unpublished course"
        )
    
    # Check if already enrolled
    is_enrolled = await course_service.is_user_enrolled(course_id, current_user.id)
    if is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled in this course"
        )
    
    enrollment = await course_service.enroll_user(course_id, current_user.id)
    
    return {
        "message": "Successfully enrolled in course",
        "course_id": course_id,
        "user_id": current_user.id,
        "enrolled_at": enrollment.created_at
    }


@router.delete("/{course_id}/enroll")
async def unenroll_from_course(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Unenroll user from a course."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if enrolled
    is_enrolled = await course_service.is_user_enrolled(course_id, current_user.id)
    if not is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enrolled in this course"
        )
    
    await course_service.unenroll_user(course_id, current_user.id)
    
    return {"message": "Successfully unenrolled from course"}


@router.get("/{course_id}/enrollments")
async def get_course_enrollments(
    course_id: int,
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get course enrollments (instructor/admin only)."""
    course_service = CourseService(db)
    
    course = await course_service.get_course_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.id != course.instructor_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view enrollments"
        )
    
    enrollments, total = await course_service.get_course_enrollments(
        course_id=course_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    return {
        "course_id": course_id,
        "enrollments": enrollments,
        "total": total,
        "skip": pagination.skip,
        "limit": pagination.limit
    }


@router.get("/categories/")
async def get_course_categories(
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all course categories."""
    course_service = CourseService(db)
    categories = await course_service.get_categories()
    
    return [
        {
            "name": category["name"],
            "count": category["count"],
            "description": category.get("description")
        }
        for category in categories
    ]