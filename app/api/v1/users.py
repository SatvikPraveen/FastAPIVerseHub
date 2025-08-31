# File: app/api/v1/users.py

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    get_pagination_params,
    get_search_params,
    PaginationParams,
    SearchParams
)
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """Get current user profile."""
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Update current user profile."""
    user_service = UserService(db)
    
    updated_user = await user_service.update_user(
        user_id=current_user.id,
        user_update=user_update
    )
    
    return UserResponse.from_orm(updated_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete current user account."""
    user_service = UserService(db)
    await user_service.delete_user(current_user.id)


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(get_pagination_params),
    search: SearchParams = Depends(get_search_params),
    is_active: bool = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """List all users (admin only)."""
    user_service = UserService(db)
    
    users, total = await user_service.get_users(
        skip=pagination.skip,
        limit=pagination.limit,
        search_query=search.query,
        is_active_filter=is_active,
        sort_by=search.sort_by,
        order=search.order
    )
    
    return {
        "items": [UserResponse.from_orm(user) for user in users],
        "total": total,
        "skip": pagination.skip,
        "limit": pagination.limit,
        "has_next": (pagination.skip + pagination.limit) < total
    }


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Create a new user (admin only)."""
    user_service = UserService(db)
    
    # Check if user already exists
    existing_user = await user_service.get_user_by_email(user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = await user_service.create_user(user_create)
    return UserResponse.from_orm(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Get user by ID."""
    user_service = UserService(db)
    
    # Users can only see their own profile unless they're superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Update user by ID."""
    user_service = UserService(db)
    
    # Users can only update their own profile unless they're superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if user exists
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Non-superusers can't change certain fields
    if not current_user.is_superuser:
        user_update.is_superuser = None
        user_update.is_active = None
    
    updated_user = await user_service.update_user(
        user_id=user_id,
        user_update=user_update
    )
    
    return UserResponse.from_orm(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete user by ID (admin only)."""
    user_service = UserService(db)
    
    # Check if user exists
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deleting yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    await user_service.delete_user(user_id)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Activate user account (admin only)."""
    user_service = UserService(db)
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )
    
    user_update = UserUpdate(is_active=True)
    updated_user = await user_service.update_user(
        user_id=user_id,
        user_update=user_update
    )
    
    return UserResponse.from_orm(updated_user)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Deactivate user account (admin only)."""
    user_service = UserService(db)
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deactivating yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already inactive"
        )
    
    user_update = UserUpdate(is_active=False)
    updated_user = await user_service.update_user(
        user_id=user_id,
        user_update=user_update
    )
    
    return UserResponse.from_orm(updated_user)


@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get user statistics."""
    user_service = UserService(db)
    
    # Users can only see their own stats unless they're superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    stats = await user_service.get_user_stats(user_id)
    
    return {
        "user_id": user_id,
        "total_courses": stats.get("total_courses", 0),
        "completed_courses": stats.get("completed_courses", 0),
        "in_progress_courses": stats.get("in_progress_courses", 0),
        "total_uploads": stats.get("total_uploads", 0),
        "account_age_days": stats.get("account_age_days", 0),
        "last_activity": stats.get("last_activity")
    }