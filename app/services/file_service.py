# File: app/services/file_service.py

from typing import Any

from sqlalchemy import Integer, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
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
        description: str | None = None,
        category: str = "general",
        is_public: bool = False,
        file_hash: str | None = None,
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

    async def get_file_by_id(self, file_id: int) -> FileUpload | None:
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
        category: str | None = None,
    ) -> tuple[list[FileUpload], int]:
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
            .values(is_deleted=True, deleted_at=utcnow())
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def update_file_metadata(
        self,
        file_id: int,
        user_id: int,
        description: str | None = None,
        category: str | None = None,
        is_public: bool | None = None,
    ) -> FileUpload | None:
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

        file_record.updated_at = utcnow()
        await self.db.commit()
        await self.db.refresh(file_record)
        return file_record

    async def update_file_info(
        self,
        file_id: int,
        description: str | None = None,
        category: str | None = None,
        is_public: bool | None = None,
    ) -> FileUpload | None:
        """Update metadata on a file the caller has already authorised.

        Ownership is enforced by the router; ``update_file_metadata`` is the
        stricter variant that re-checks ``user_id``.
        """
        file_record = await self.get_file_by_id(file_id)
        if not file_record:
            return None
        if description is not None:
            file_record.description = description
        if category is not None:
            file_record.category = category
        if is_public is not None:
            file_record.is_public = is_public
        file_record.updated_at = utcnow()
        await self.db.commit()
        await self.db.refresh(file_record)
        return file_record

    async def increment_download_count(self, file_id: int) -> None:
        """Atomically bump the download counter (no read-modify-write race)."""
        await self.db.execute(
            update(FileUpload)
            .where(FileUpload.id == file_id)
            .values(download_count=FileUpload.download_count + 1)
        )
        await self.db.commit()

    async def get_categories_with_counts(self, user_id: int) -> list[dict[str, Any]]:
        """Return ``[{"name": category, "count": n}, ...]`` for a user's live files."""
        query = (
            select(FileUpload.category, func.count(FileUpload.id))
            .where(and_(FileUpload.user_id == user_id, FileUpload.is_deleted.is_(False)))
            .group_by(FileUpload.category)
            .order_by(func.count(FileUpload.id).desc())
        )
        result = await self.db.execute(query)
        return [{"name": name or "general", "count": count} for name, count in result.all()]

    async def get_user_file_stats(self, user_id: int) -> dict[str, Any]:
        """Aggregate storage statistics for a user in a single round trip."""
        live = and_(FileUpload.user_id == user_id, FileUpload.is_deleted.is_(False))
        query = select(
            func.count(FileUpload.id),
            func.coalesce(func.sum(FileUpload.file_size), 0),
            func.coalesce(func.sum(FileUpload.download_count), 0),
            func.coalesce(func.sum(func.cast(FileUpload.is_public, Integer)), 0),
        ).where(live)
        total_files, total_size, total_downloads, public_files = (
            await self.db.execute(query)
        ).one()
        categories = {
            item["name"]: item["count"] for item in await self.get_categories_with_counts(user_id)
        }
        return {
            "total_files": int(total_files or 0),
            "total_size_bytes": int(total_size or 0),
            "public_files": int(public_files or 0),
            "private_files": int(total_files or 0) - int(public_files or 0),
            "total_downloads": int(total_downloads or 0),
            "categories": categories,
        }
