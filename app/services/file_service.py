# File: app/services/file_service.py

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import FileUpload


class FileService:
    """Service for file record management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_file_record(
        self,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        content_type: str,
        user_id: int,
        description: Optional[str] = None,
        category: str = "general",
        is_public: bool = False,
        file_hash: Optional[str] = None,
    ) -> FileUpload:
        """Create a new file record in the database."""
        file_record = FileUpload(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            content_type=content_type,
            file_hash=file_hash,
            category=category,
            description=description,
            is_public=is_public,
        )
        self.db.add(file_record)
        await self.db.commit()
        await self.db.refresh(file_record)
        return file_record

    async def get_file_by_id(self, file_id: int) -> Optional[FileUpload]:
        """Retrieve a file record by its ID."""
        query = select(FileUpload).where(
            and_(FileUpload.id == file_id, FileUpload.is_deleted.is_(False))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_files(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        category: Optional[str] = None,
    ) -> Tuple[List[FileUpload], int]:
        """Return paginated file records for a user."""
        base_filter = and_(FileUpload.user_id == user_id, FileUpload.is_deleted.is_(False))
        if category:
            base_filter = and_(base_filter, FileUpload.category == category)

        count_q = select(func.count(FileUpload.id)).where(base_filter)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0

        query = (
            select(FileUpload)
            .where(base_filter)
            .order_by(FileUpload.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        files = list(result.scalars().all())
        return files, total

    async def delete_file(self, file_id: int, user_id: int) -> bool:
        """Soft-delete a file record (only the owning user may delete)."""
        query = (
            update(FileUpload)
            .where(and_(FileUpload.id == file_id, FileUpload.user_id == user_id))
            .values(is_deleted=True, deleted_at=datetime.utcnow())
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def update_file_metadata(
        self,
        file_id: int,
        user_id: int,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Optional[FileUpload]:
        """Update mutable metadata fields of a file record."""
        file_record = await self.get_file_by_id(file_id)
        if not file_record or file_record.user_id != user_id:
            return None

        if description is not None:
            file_record.description = description
        if category is not None:
            file_record.category = category
        if is_public is not None:
            file_record.is_public = is_public

        file_record.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(file_record)
        return file_record
