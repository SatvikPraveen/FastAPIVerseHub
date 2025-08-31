# File: app/api/v1/uploads.py

import mimetypes
import os
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.file_utils import FileManager
from app.core.config import settings
from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.services.file_service import FileService

router = APIRouter()


@router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form("general"),
    is_public: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Upload a single file."""
    file_service = FileService(db)
    file_manager = FileManager()
    
    # Validate file
    await file_manager.validate_file(file)
    
    # Save file
    saved_file = await file_manager.save_file(file, current_user.id)
    
    # Create file record in database
    file_record = await file_service.create_file_record(
        filename=saved_file["filename"],
        original_filename=file.filename,
        file_path=saved_file["file_path"],
        file_size=saved_file["file_size"],
        content_type=file.content_type,
        user_id=current_user.id,
        description=description,
        category=category,
        is_public=is_public
    )
    
    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "original_filename": file_record.original_filename,
        "file_size": file_record.file_size,
        "content_type": file_record.content_type,
        "category": file_record.category,
        "is_public": file_record.is_public,
        "upload_url": f"/api/v1/uploads/file/{file_record.id}",
        "download_url": f"/api/v1/uploads/download/{file_record.id}",
        "created_at": file_record.created_at
    }


@router.post("/multiple", status_code=status.HTTP_201_CREATED)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form("general"),
    is_public: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Upload multiple files."""
    if len(files) > 10:  # Limit number of files
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many files. Maximum 10 files allowed."
        )
    
    file_service = FileService(db)
    file_manager = FileManager()
    uploaded_files = []
    failed_files = []
    
    for file in files:
        try:
            # Validate file
            await file_manager.validate_file(file)
            
            # Save file
            saved_file = await file_manager.save_file(file, current_user.id)
            
            # Create file record
            file_record = await file_service.create_file_record(
                filename=saved_file["filename"],
                original_filename=file.filename,
                file_path=saved_file["file_path"],
                file_size=saved_file["file_size"],
                content_type=file.content_type,
                user_id=current_user.id,
                description=description,
                category=category,
                is_public=is_public
            )
            
            uploaded_files.append({
                "id": file_record.id,
                "filename": file_record.filename,
                "original_filename": file_record.original_filename,
                "file_size": file_record.file_size,
                "download_url": f"/api/v1/uploads/download/{file_record.id}"
            })
            
        except Exception as e:
            failed_files.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "uploaded_files": uploaded_files,
        "failed_files": failed_files,
        "total_uploaded": len(uploaded_files),
        "total_failed": len(failed_files)
    }


@router.get("/", response_model=PaginatedResponse)
async def list_files(
    skip: int = 0,
    limit: int = 20,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """List user's uploaded files."""
    file_service = FileService(db)
    
    files, total = await file_service.get_user_files(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        category=category
    )
    
    file_list = []
    for file_record in files:
        file_list.append({
            "id": file_record.id,
            "filename": file_record.filename,
            "original_filename": file_record.original_filename,
            "file_size": file_record.file_size,
            "content_type": file_record.content_type,
            "category": file_record.category,
            "is_public": file_record.is_public,
            "description": file_record.description,
            "download_url": f"/api/v1/uploads/download/{file_record.id}",
            "created_at": file_record.created_at
        })
    
    return {
        "items": file_list,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_next": (skip + limit) < total
    }


@router.get("/file/{file_id}")
async def get_file_info(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get file information."""
    file_service = FileService(db)
    
    file_record = await file_service.get_file_by_id(file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check permissions
    if not file_record.is_public and file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "original_filename": file_record.original_filename,
        "file_size": file_record.file_size,
        "content_type": file_record.content_type,
        "category": file_record.category,
        "is_public": file_record.is_public,
        "description": file_record.description,
        "download_url": f"/api/v1/uploads/download/{file_record.id}",
        "stream_url": f"/api/v1/uploads/stream/{file_record.id}",
        "created_at": file_record.created_at,
        "updated_at": file_record.updated_at
    }


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Download file."""
    file_service = FileService(db)
    
    file_record = await file_service.get_file_by_id(file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check permissions
    if not file_record.is_public and file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if file exists on disk
    if not os.path.exists(file_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    # Update download count
    await file_service.increment_download_count(file_id)
    
    # Return file
    return FileResponse(
        path=file_record.file_path,
        filename=file_record.original_filename,
        media_type=file_record.content_type
    )


@router.get("/stream/{file_id}")
async def stream_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Stream file (useful for large files or media)."""
    file_service = FileService(db)
    
    file_record = await file_service.get_file_by_id(file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check permissions
    if not file_record.is_public and file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if file exists
    if not os.path.exists(file_record.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    file_manager = FileManager()
    
    return StreamingResponse(
        file_manager.stream_file(file_record.file_path),
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f"inline; filename={file_record.original_filename}"
        }
    )


@router.put("/file/{file_id}")
async def update_file_info(
    file_id: int,
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Update file information."""
    file_service = FileService(db)
    
    file_record = await file_service.get_file_by_id(file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check ownership
    if file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your file"
        )
    
    updated_file = await file_service.update_file_info(
        file_id=file_id,
        description=description,
        category=category,
        is_public=is_public
    )
    
    return {
        "id": updated_file.id,
        "filename": updated_file.filename,
        "original_filename": updated_file.original_filename,
        "description": updated_file.description,
        "category": updated_file.category,
        "is_public": updated_file.is_public,
        "updated_at": updated_file.updated_at
    }


@router.delete("/file/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete file."""
    file_service = FileService(db)
    file_manager = FileManager()
    
    file_record = await file_service.get_file_by_id(file_id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check ownership
    if file_record.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Delete physical file
    await file_manager.delete_file(file_record.file_path)
    
    # Delete database record
    await file_service.delete_file(file_id)


@router.get("/categories")
async def get_file_categories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get file categories with counts."""
    file_service = FileService(db)
    
    categories = await file_service.get_categories_with_counts(current_user.id)
    
    return {"categories": categories}


@router.get("/stats")
async def get_file_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get user's file upload statistics."""
    file_service = FileService(db)
    
    stats = await file_service.get_user_file_stats(current_user.id)
    
    return {
        "total_files": stats["total_files"],
        "total_size_bytes": stats["total_size_bytes"],
        "total_size_mb": round(stats["total_size_bytes"] / (1024 * 1024), 2),
        "public_files": stats["public_files"],
        "private_files": stats["private_files"],
        "total_downloads": stats["total_downloads"],
        "categories": stats["categories"]
    }