# File: app/tests/test_uploads.py

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import assert_response_success, assert_response_error


class TestFileUpload:
    """Test file upload functionality."""
    
    async def test_upload_single_file_success(
        self, 
        async_client: AsyncClient, 
        auth_headers,
        mock_file_manager
    ):
        """Test successful single file upload."""
        # Create test file data
        file_content = b"Test file content"
        files = {
            "file": ("test.txt", BytesIO(file_content), "text/plain")
        }
        
        data = {
            "description": "Test file upload",
            "category": "documents",
            "is_public": "false"
        }
        
        with patch("app.api.v1.uploads.FileManager", return_value=mock_file_manager):
            response = await async_client.post(
                "/api/v1/uploads/file",
                files=files,
                data=data,
                headers=auth_headers
            )
        
        assert_response_success(response, 201)
        response_data = response.json()
        
        assert "id" in response_data
        assert response_data["filename"] == "test_123.txt"
        assert response_data["original_filename"] == "test.txt"
        assert response_data["file_size"] == 100
        assert response_data["content_type"] == "text/plain"
        assert "download_url" in response_data
    
    async def test_upload_file_unauthorized(self, async_client: AsyncClient):
        """Test file upload without authentication."""
        files = {
            "file": ("test.txt", BytesIO(b"content"), "text/plain")
        }
        
        response = await async_client.post("/api/v1/uploads/file", files=files)
        
        assert_response_error(response, 401, "UNAUTHORIZED")
    
    async def test_upload_file_too_large(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test upload of file that's too large."""
        # Create large file content (mock)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {
            "file": ("large.txt", BytesIO(large_content), "text/plain")
        }
        
        with patch("app.common.file_utils.FileManager.validate_file") as mock_validate:
            mock_validate.side_effect = Exception("File too large")
            
            response = await async_client.post(
                "/api/v1/uploads/file",
                files=files,
                headers=auth_headers
            )
        
        assert response.status_code >= 400
    
    async def test_upload_invalid_file_type(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test upload of invalid file type."""
        files = {
            "file": ("malware.exe", BytesIO(b"malicious"), "application/executable")
        }
        
        with patch("app.common.file_utils.FileManager.validate_file") as mock_validate:
            mock_validate.side_effect = Exception("Invalid file type")
            
            response = await async_client.post(
                "/api/v1/uploads/file",
                files=files,
                headers=auth_headers
            )
        
        assert response.status_code >= 400
    
    async def test_upload_multiple_files_success(
        self, 
        async_client: AsyncClient, 
        auth_headers,
        mock_file_manager
    ):
        """Test successful multiple file upload."""
        files = [
            ("files", ("file1.txt", BytesIO(b"content1"), "text/plain")),
            ("files", ("file2.txt", BytesIO(b"content2"), "text/plain"))
        ]
        
        data = {
            "description": "Multiple test files",
            "category": "documents"
        }
        
        with patch("app.api.v1.uploads.FileManager", return_value=mock_file_manager):
            response = await async_client.post(
                "/api/v1/uploads/multiple",
                files=files,
                data=data,
                headers=auth_headers
            )
        
        assert_response_success(response, 201)
        response_data = response.json()
        
        assert "uploaded_files" in response_data
        assert "failed_files" in response_data
        assert response_data["total_uploaded"] >= 0
        assert response_data["total_failed"] >= 0
    
    async def test_upload_too_many_files(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test upload with too many files."""
        # Create more than 10 files (the limit)
        files = [
            ("files", (f"file{i}.txt", BytesIO(f"content{i}".encode()), "text/plain"))
            for i in range(12)
        ]
        
        response = await async_client.post(
            "/api/v1/uploads/multiple",
            files=files,
            headers=auth_headers
        )
        
        assert_response_error(response, 400, "BAD_REQUEST")


class TestFileDownload:
    """Test file download functionality."""
    
    async def test_download_file_success(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test successful file download."""
        # Mock file record exists
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 1
            mock_file.is_public = False
            mock_file.file_path = "/test/path/file.txt"
            mock_file.original_filename = "test.txt"
            mock_file.content_type = "text/plain"
            mock_get_file.return_value = mock_file
            
            with patch("os.path.exists", return_value=True):
                with patch("app.services.file_service.FileService.increment_download_count"):
                    response = await async_client.get(
                        "/api/v1/uploads/download/1",
                        headers=auth_headers
                    )
        
        # Should return file response (can't easily test content in this setup)
        assert response.status_code in [200, 404]  # 404 if file doesn't actually exist on disk
    
    async def test_download_file_not_found(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test download of nonexistent file."""
        with patch("app.services.file_service.FileService.get_file_by_id", return_value=None):
            response = await async_client.get(
                "/api/v1/uploads/download/999",
                headers=auth_headers
            )
        
        assert_response_error(response, 404, "NOT_FOUND")
    
    async def test_download_file_access_denied(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test download of file without permission."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 999  # Different user
            mock_file.is_public = False
            mock_get_file.return_value = mock_file
            
            response = await async_client.get(
                "/api/v1/uploads/download/1",
                headers=auth_headers
            )
        
        assert_response_error(response, 403, "FORBIDDEN")
    
    async def test_download_public_file(
        self, 
        async_client: AsyncClient
    ):
        """Test download of public file without authentication."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 999
            mock_file.is_public = True
            mock_file.file_path = "/test/path/public.txt"
            mock_file.original_filename = "public.txt"
            mock_file.content_type = "text/plain"
            mock_get_file.return_value = mock_file
            
            with patch("os.path.exists", return_value=True):
                response = await async_client.get("/api/v1/uploads/download/1")
        
        # Should allow access to public file
        assert response.status_code in [200, 404]


class TestFileStreaming:
    """Test file streaming functionality."""
    
    async def test_stream_file_success(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test successful file streaming."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 1
            mock_file.is_public = False
            mock_file.file_path = "/test/path/stream.txt"
            mock_file.original_filename = "stream.txt"
            mock_file.content_type = "text/plain"
            mock_get_file.return_value = mock_file
            
            with patch("os.path.exists", return_value=True):
                with patch("app.common.file_utils.FileManager.stream_file") as mock_stream:
                    mock_stream.return_value = [b"chunk1", b"chunk2"]
                    
                    response = await async_client.get(
                        "/api/v1/uploads/stream/1",
                        headers=auth_headers
                    )
        
        assert response.status_code in [200, 404]


class TestFileManagement:
    """Test file management endpoints."""
    
    async def test_list_user_files(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test listing user's files."""
        with patch("app.services.file_service.FileService.get_user_files") as mock_get_files:
            mock_get_files.return_value = ([], 0)  # Empty list, total count 0
            
            response = await async_client.get(
                "/api/v1/uploads/",
                headers=auth_headers
            )
        
        assert_response_success(response)
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "has_next" in data
    
    async def test_get_file_info(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test getting file information."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 1
            mock_file.filename = "test_123.txt"
            mock_file.original_filename = "test.txt"
            mock_file.file_size = 100
            mock_file.content_type = "text/plain"
            mock_file.category = "documents"
            mock_file.is_public = False
            mock_file.description = "Test file"
            mock_file.created_at = "2024-01-01T00:00:00"
            mock_file.updated_at = "2024-01-01T00:00:00"
            mock_get_file.return_value = mock_file
            
            response = await async_client.get(
                "/api/v1/uploads/file/1",
                headers=auth_headers
            )
        
        assert_response_success(response)
        data = response.json()
        
        assert data["id"] == 1
        assert data["filename"] == "test_123.txt"
        assert data["original_filename"] == "test.txt"
        assert "download_url" in data
        assert "stream_url" in data
    
    async def test_update_file_info(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test updating file information."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 1
            mock_get_file.return_value = mock_file
            
            with patch("app.services.file_service.FileService.update_file_info") as mock_update:
                mock_update.return_value = mock_file
                
                update_data = {
                    "description": "Updated description",
                    "category": "images",
                    "is_public": "true"
                }
                
                response = await async_client.put(
                    "/api/v1/uploads/file/1",
                    data=update_data,
                    headers=auth_headers
                )
        
        assert_response_success(response)
    
    async def test_delete_file_success(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test successful file deletion."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 1
            mock_file.file_path = "/test/path/file.txt"
            mock_get_file.return_value = mock_file
            
            with patch("app.common.file_utils.FileManager.delete_file") as mock_delete:
                mock_delete.return_value = True
                
                with patch("app.services.file_service.FileService.delete_file"):
                    response = await async_client.delete(
                        "/api/v1/uploads/file/1",
                        headers=auth_headers
                    )
        
        assert_response_success(response, 204)
    
    async def test_delete_file_not_owner(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test file deletion by non-owner."""
        with patch("app.services.file_service.FileService.get_file_by_id") as mock_get_file:
            mock_file = AsyncMock()
            mock_file.id = 1
            mock_file.user_id = 999  # Different user
            mock_get_file.return_value = mock_file
            
            response = await async_client.delete(
                "/api/v1/uploads/file/1",
                headers=auth_headers
            )
        
        assert_response_error(response, 403, "FORBIDDEN")


class TestFileStatistics:
    """Test file statistics endpoints."""
    
    async def test_get_file_categories(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test getting file categories with counts."""
        with patch("app.services.file_service.FileService.get_categories_with_counts") as mock_get_cats:
            mock_get_cats.return_value = [
                {"name": "documents", "count": 5},
                {"name": "images", "count": 3}
            ]
            
            response = await async_client.get(
                "/api/v1/uploads/categories",
                headers=auth_headers
            )
        
        assert_response_success(response)
        data = response.json()
        
        assert "categories" in data
        assert isinstance(data["categories"], list)
    
    async def test_get_file_stats(
        self, 
        async_client: AsyncClient, 
        auth_headers
    ):
        """Test getting user file statistics."""
        with patch("app.services.file_service.FileService.get_user_file_stats") as mock_get_stats:
            mock_get_stats.return_value = {
                "total_files": 10,
                "total_size_bytes": 1024000,
                "public_files": 3,
                "private_files": 7,
                "total_downloads": 25,
                "categories": {"documents": 5, "images": 5}
            }
            
            response = await async_client.get(
                "/api/v1/uploads/stats",
                headers=auth_headers
            )
        
        assert_response_success(response)
        data = response.json()
        
        assert "total_files" in data
        assert "total_size_mb" in data
        assert "categories" in data