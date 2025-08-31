# File: app/tests/test_sse.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import assert_response_success, assert_response_error


class TestSSEConnection:
    """Test Server-Sent Events connection functionality."""
    
    async def test_sse_connect_success(self, async_client: AsyncClient):
        """Test successful SSE connection."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.get_messages_for_client = AsyncMock(return_value=[])
            mock_sse_manager.remove_client = AsyncMock()
            
            # This would normally stream, but we can test the endpoint exists
            response = await async_client.get("/api/v1/sse/events")
            
            # SSE endpoint should return 200 and start streaming
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
    
    async def test_sse_connect_with_channels(self, async_client: AsyncClient):
        """Test SSE connection with channel subscription."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.get_messages_for_client = AsyncMock(return_value=[])
            mock_sse_manager.subscribe_to_channel = AsyncMock()
            mock_sse_manager.remove_client = AsyncMock()
            
            response = await async_client.get("/api/v1/sse/events?channels=general,updates")
            
            assert response.status_code == 200
    
    async def test_sse_connect_authenticated(self, async_client: AsyncClient, auth_headers):
        """Test SSE connection with authentication."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.get_messages_for_client = AsyncMock(return_value=[])
            mock_sse_manager.subscribe_to_user_events = AsyncMock()
            mock_sse_manager.remove_client = AsyncMock()
            
            response = await async_client.get("/api/v1/sse/events", headers=auth_headers)
            
            assert response.status_code == 200


class TestSSEPublishing:
    """Test SSE message publishing functionality."""
    
    async def test_publish_to_channel_success(self, async_client: AsyncClient, auth_headers):
        """Test successful message publishing to channel."""
        message_data = {
            "type": "announcement",
            "content": "New feature released!",
            "title": "Product Update",
            "metadata": {"priority": "high"}
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock(return_value=5)
            
            response = await async_client.post(
                "/api/v1/sse/publish/announcements",
                json=message_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "published" in data["message"].lower()
            assert "event_id" in data
            assert data["event_id"].startswith("msg_")
    
    async def test_publish_to_nonexistent_channel(self, async_client: AsyncClient, auth_headers):
        """Test publishing to channel with no subscribers."""
        message_data = {
            "content": "Message to empty channel"
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock(return_value=0)
            
            response = await async_client.post(
                "/api/v1/sse/publish/empty-channel",
                json=message_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
    
    async def test_publish_unauthorized(self, async_client: AsyncClient):
        """Test publishing without authentication."""
        message_data = {
            "content": "Unauthorized message"
        }
        
        response = await async_client.post(
            "/api/v1/sse/publish/test-channel",
            json=message_data
        )
        
        # Should still work for public publishing, or return 401 if auth required
        assert response.status_code in [200, 401]


class TestSSEUserNotifications:
    """Test SSE user-specific notifications."""
    
    async def test_notify_user_success(self, async_client: AsyncClient, auth_headers):
        """Test sending notification to specific user."""
        notification_data = {
            "title": "Course Completed",
            "content": "Congratulations on completing the Python course!",
            "priority": "normal",
            "action_url": "/courses/123",
            "metadata": {"course_id": 123}
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.send_to_user = AsyncMock(return_value=True)
            
            response = await async_client.post(
                "/api/v1/sse/notify/user/456",
                json=notification_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "notification sent" in data["message"].lower()
            assert data["delivered"] is True
            assert "event_id" in data
    
    async def test_notify_offline_user(self, async_client: AsyncClient, auth_headers):
        """Test sending notification to offline user."""
        notification_data = {
            "title": "Test Notification",
            "content": "This user is offline"
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.send_to_user = AsyncMock(return_value=False)
            
            response = await async_client.post(
                "/api/v1/sse/notify/user/999",
                json=notification_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert data["delivered"] is False
    
    async def test_notify_user_invalid_data(self, async_client: AsyncClient, auth_headers):
        """Test notification with invalid data."""
        invalid_data = {
            # Missing required fields
            "metadata": {"test": True}
        }
        
        response = await async_client.post(
            "/api/v1/sse/notify/user/123",
            json=invalid_data,
            headers=auth_headers
        )
        
        # Should still process with defaults
        assert response.status_code in [200, 422]


class TestSSEBroadcast:
    """Test SSE broadcast functionality."""
    
    async def test_broadcast_success(self, async_client: AsyncClient, auth_headers):
        """Test successful broadcast to multiple channels."""
        broadcast_data = {
            "title": "System Maintenance",
            "content": "The system will be down for maintenance in 1 hour.",
            "metadata": {"type": "maintenance", "duration": "2 hours"}
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock(return_value=10)
            
            response = await async_client.post(
                "/api/v1/sse/broadcast?channels=general,announcements,alerts",
                json=broadcast_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "broadcasted" in data["message"].lower()
            assert data["total_recipients"] > 0
            assert "channels" in data
            assert len(data["channels"]) == 3
    
    async def test_broadcast_default_channel(self, async_client: AsyncClient, auth_headers):
        """Test broadcast without specifying channels (uses default)."""
        broadcast_data = {
            "content": "General announcement"
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock(return_value=5)
            
            response = await async_client.post(
                "/api/v1/sse/broadcast",
                json=broadcast_data,
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "general" in data["channels"]
    
    async def test_broadcast_empty_message(self, async_client: AsyncClient, auth_headers):
        """Test broadcast with empty message."""
        empty_data = {}
        
        response = await async_client.post(
            "/api/v1/sse/broadcast",
            json=empty_data,
            headers=auth_headers
        )
        
        # Should still work with defaults
        assert_response_success(response)


class TestSSEStatistics:
    """Test SSE statistics and monitoring."""
    
    async def test_get_sse_stats(self, async_client: AsyncClient):
        """Test getting SSE statistics."""
        mock_stats = {
            "total_clients": 25,
            "authenticated_clients": 18,
            "active_channels": 5,
            "total_messages_sent": 1500,
            "uptime_seconds": 3600
        }
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.get_stats = AsyncMock(return_value=mock_stats)
            
            response = await async_client.get("/api/v1/sse/stats")
            
            assert_response_success(response)
            data = response.json()
            
            assert data["total_clients"] == 25
            assert data["authenticated_clients"] == 18
            assert data["active_channels"] == 5
            assert data["total_messages_sent"] == 1500
            assert data["uptime_seconds"] == 3600
    
    async def test_list_active_channels(self, async_client: AsyncClient):
        """Test listing active SSE channels."""
        mock_channels = [
            {
                "name": "general",
                "subscriber_count": 10,
                "last_message_at": "2024-01-01T12:00:00"
            },
            {
                "name": "announcements", 
                "subscriber_count": 5,
                "last_message_at": "2024-01-01T11:30:00"
            }
        ]
        
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.get_active_channels = AsyncMock(return_value=mock_channels)
            
            response = await async_client.get("/api/v1/sse/channels")
            
            assert_response_success(response)
            data = response.json()
            
            assert "channels" in data
            assert len(data["channels"]) == 2
            assert data["channels"][0]["name"] == "general"
            assert data["channels"][0]["subscriber_count"] == 10
    
    async def test_clear_channel(self, async_client: AsyncClient, auth_headers):
        """Test clearing messages from a channel."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.clear_channel = AsyncMock(return_value=25)
            
            response = await async_client.delete(
                "/api/v1/sse/channels/test-channel",
                headers=auth_headers
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "cleared" in data["message"].lower()
            assert data["messages_cleared"] == 25


class TestSSETestingEndpoints:
    """Test SSE testing and development endpoints."""
    
    async def test_send_test_events(self, async_client: AsyncClient):
        """Test sending test events to a channel."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock()
            
            response = await async_client.post(
                "/api/v1/sse/test/events?channel=test&count=3&interval=0.1"
            )
            
            assert_response_success(response)
            data = response.json()
            
            assert "sent 3 test events" in data["message"].lower()
            assert data["channel"] == "test"
            assert len(data["event_ids"]) == 3
    
    async def test_send_test_events_default_params(self, async_client: AsyncClient):
        """Test sending test events with default parameters."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock()
            
            response = await async_client.post("/api/v1/sse/test/events")
            
            assert_response_success(response)
            data = response.json()
            
            assert "sent 5 test events" in data["message"].lower()
            assert data["channel"] == "test"
    
    async def test_send_test_events_max_limit(self, async_client: AsyncClient):
        """Test sending test events with maximum allowed count."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock()
            
            response = await async_client.post(
                "/api/v1/sse/test/events?count=100"  # Over the limit
            )
            
            # Should be limited to 50 or return validation error
            assert response.status_code in [200, 422]


class TestSSEErrorHandling:
    """Test SSE error handling scenarios."""
    
    async def test_sse_manager_exception(self, async_client: AsyncClient):
        """Test handling of SSE manager exceptions."""
        with patch("app.api.v1.sse.sse_manager") as mock_sse_manager:
            mock_sse_manager.publish_to_channel = AsyncMock(side_effect=Exception("SSE Error"))
            
            response = await async_client.post(
                "/api/v1/sse/publish/error-channel",
                json={"content": "Test message"}
            )
            
            # Should handle gracefully
            assert response.status_code >= 500
    
    async def test_invalid_channel_name(self, async_client: AsyncClient, auth_headers):
        """Test publishing to channel with invalid name."""
        message_data = {
            "content": "Test message"
        }
        
        # Test with potentially problematic channel names
        invalid_channels = ["", "channel with spaces", "channel/with/slashes"]
        
        for channel in invalid_channels:
            response = await async_client.post(
                f"/api/v1/sse/publish/{channel}",
                json=message_data,
                headers=auth_headers
            )
            
            # Should either work or return appropriate error
            assert response.status_code in [200, 400, 422]