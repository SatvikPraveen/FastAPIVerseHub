# File: app/common/file_utils.py

import os
import uuid
import mimetypes
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, BinaryIO

import aiofiles
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.core.config import settings


class FileManager:
    """File handling utilities with validation and processing."""
    
    def __init__(self):
        self.upload_path = Path(settings.UPLOAD_PATH)
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = settings.allowed_extensions_list
        
        # Ensure upload directory exists
        self.upload_path.mkdir(parents=True, exist_ok=True)
    
    async def validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check file size
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {file.size} exceeds maximum allowed size {self.max_file_size}"
            )
        
        # Check file extension
        if file.filename:
            extension = Path(file.filename).suffix.lower().lstrip('.')
            if extension not in self.allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File extension '{extension}' not allowed. Allowed: {', '.join(self.allowed_extensions)}"
                )
        
        # Check MIME type
        if file.content_type:
            expected_mime = mimetypes.guess_type(file.filename)[0]
            if expected_mime and not file.content_type.startswith(expected_mime.split('/')[0]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"MIME type mismatch. Expected: {expected_mime}, Got: {file.content_type}"
                )
    
    async def save_file(
        self, 
        file: UploadFile, 
        user_id: int,
        subfolder: Optional[str] = None
    ) -> Dict[str, any]:
        """Save uploaded file to disk."""
        # Generate unique filename
        file_extension = Path(file.filename).suffix if file.filename else ""
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Create user subfolder
        user_folder = self.upload_path / str(user_id)
        if subfolder:
            user_folder = user_folder / subfolder
        
        user_folder.mkdir(parents=True, exist_ok=True)
        
        file_path = user_folder / unique_filename
        
        # Calculate file hash while saving
        hasher = hashlib.sha256()
        file_size = 0
        
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):  # 8KB chunks
                hasher.update(chunk)
                file_size += len(chunk)
                await f.write(chunk)
        
        # Reset file position for potential reuse
        await file.seek(0)
        
        return {
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "file_hash": hasher.hexdigest(),
            "content_type": file.content_type
        }
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from disk."""
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
        except Exception:
            pass
        return False
    
    async def stream_file(self, file_path: str, chunk_size: int = 8192) -> AsyncGenerator[bytes, None]:
        """Stream file in chunks."""
        async with aiofiles.open(file_path, 'rb') as file:
            while chunk := await file.read(chunk_size):
                yield chunk
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, any]]:
        """Get file information."""
        path = Path(file_path)
        if not path.exists():
            return None
        
        stat = path.stat()
        return {
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "mime_type": mimetypes.guess_type(str(path))[0],
            "extension": path.suffix.lower().lstrip('.')
        }
    
    async def create_thumbnail(
        self,
        image_path: str,
        thumbnail_size: tuple = (150, 150),
        quality: int = 85
    ) -> Optional[str]:
        """Create thumbnail for image files."""
        try:
            path = Path(image_path)
            if not path.exists():
                return None
            
            # Check if it's an image
            if not self.is_image(str(path)):
                return None
            
            # Generate thumbnail path
            thumbnail_name = f"thumb_{path.stem}.jpg"
            thumbnail_path = path.parent / thumbnail_name
            
            # Create thumbnail
            with Image.open(path) as image:
                # Convert RGBA to RGB for JPEG
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                # Create thumbnail with aspect ratio preserved
                image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
                
                # Save thumbnail
                image.save(thumbnail_path, 'JPEG', quality=quality, optimize=True)
            
            return str(thumbnail_path)
            
        except Exception:
            return None
    
    def is_image(self, file_path: str) -> bool:
        """Check if file is an image."""
        image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in image_extensions
    
    def is_video(self, file_path: str) -> bool:
        """Check if file is a video."""
        video_extensions = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in video_extensions
    
    def is_audio(self, file_path: str) -> bool:
        """Check if file is audio."""
        audio_extensions = {'mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'wma'}
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in audio_extensions
    
    def is_document(self, file_path: str) -> bool:
        """Check if file is a document."""
        doc_extensions = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'xls', 'xlsx', 'ppt', 'pptx'}
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in doc_extensions
    
    async def get_file_metadata(self, file_path: str) -> Dict[str, any]:
        """Extract file metadata."""
        info = self.get_file_info(file_path)
        if not info:
            return {}
        
        metadata = {
            "basic_info": info,
            "file_type": self._get_file_type(file_path)
        }
        
        # Add type-specific metadata
        if self.is_image(file_path):
            metadata["image_info"] = await self._get_image_metadata(file_path)
        elif self.is_video(file_path):
            metadata["video_info"] = await self._get_video_metadata(file_path)
        elif self.is_audio(file_path):
            metadata["audio_info"] = await self._get_audio_metadata(file_path)
        
        return metadata
    
    def _get_file_type(self, file_path: str) -> str:
        """Determine file type category."""
        if self.is_image(file_path):
            return "image"
        elif self.is_video(file_path):
            return "video"
        elif self.is_audio(file_path):
            return "audio"
        elif self.is_document(file_path):
            return "document"
        else:
            return "other"
    
    async def _get_image_metadata(self, file_path: str) -> Dict[str, any]:
        """Get image-specific metadata."""
        try:
            with Image.open(file_path) as image:
                return {
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "format": image.format,
                    "has_transparency": image.mode in ('RGBA', 'LA', 'P'),
                    "exif": dict(image.getexif()) if hasattr(image, 'getexif') else {}
                }
        except Exception:
            return {}
    
    async def _get_video_metadata(self, file_path: str) -> Dict[str, any]:
        """Get video-specific metadata."""
        # Placeholder for video metadata extraction
        # Would require ffmpeg-python or similar
        return {
            "duration": None,
            "width": None,
            "height": None,
            "codec": None,
            "bitrate": None
        }
    
    async def _get_audio_metadata(self, file_path: str) -> Dict[str, any]:
        """Get audio-specific metadata."""
        # Placeholder for audio metadata extraction
        # Would require mutagen or similar
        return {
            "duration": None,
            "bitrate": None,
            "sample_rate": None,
            "channels": None,
            "title": None,
            "artist": None,
            "album": None
        }
    
    async def optimize_image(
        self,
        image_path: str,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 85
    ) -> str:
        """Optimize image file size and dimensions."""
        try:
            path = Path(image_path)
            optimized_name = f"opt_{path.stem}.jpg"
            optimized_path = path.parent / optimized_name
            
            with Image.open(path) as image:
                # Convert to RGB for JPEG
                if image.mode in ('RGBA', 'LA', 'P'):
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = rgb_image
                
                # Resize if too large
                if image.width > max_width or image.height > max_height:
                    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Save optimized image
                image.save(optimized_path, 'JPEG', quality=quality, optimize=True)
            
            return str(optimized_path)
            
        except Exception:
            return image_path  # Return original if optimization fails
    
    def clean_filename(self, filename: str) -> str:
        """Clean and sanitize filename."""
        # Remove or replace dangerous characters
        unsafe_chars = '<>:"/\\|?*'
        cleaned = filename
        
        for char in unsafe_chars:
            cleaned = cleaned.replace(char, '_')
        
        # Limit length
        name_part = Path(cleaned).stem[:100]
        extension = Path(cleaned).suffix[:10]
        
        return f"{name_part}{extension}"
    
    async def get_directory_size(self, directory_path: str) -> int:
        """Calculate total size of directory."""
        total_size = 0
        path = Path(directory_path)
        
        if not path.exists():
            return 0
        
        for file_path in path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    async def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up files older than specified days."""
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
        deleted_count = 0
        
        for file_path in self.upload_path.rglob('*'):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_date:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception:
                    continue
        
        return deleted_count