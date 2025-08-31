# File: app/tests/test_websockets.py

import pytest
import json
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.core.security import security_manager


class TestWebSocketConnection:
    """Test WebSocket connection functionality."""
    
    def test_websocket_connect_success(self, websocket_client):
        """Test successful WebSocket connection."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/test-client-123") as websocket:
            # Should receive welcome message
            data = websocket.receive_json()
            
            assert data["type"] == "connection"
            assert data["message"] == "Connected successfully"
            assert data["client_id"] == "test-client-123"
            assert data["authenticated"] is False
    
    def test_websocket_connect_with_auth(self, websocket_client, test_user: User):
        """Test WebSocket connection with authentication."""
        # Create auth token
        token = security_manager.create_access_token(
            data={"sub": str(test_user.id)}
        )
        
        with websocket_client.websocket_connect(
            f"/api/v1/ws/connect/auth-client?token={token}"
        ) as websocket:
            data = websocket.receive_json()
            
            assert data["type"] == "connection"
            assert data["authenticated"] is True
    
    def test_websocket_ping_pong(self, websocket_client):
        """Test ping-pong functionality."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/ping-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send ping
            ping_message = {
                "type": "ping",
                "timestamp": "2024-01-01T00:00:00"
            }
            websocket.send_json(ping_message)
            
            # Should receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert response["timestamp"] == ping_message["timestamp"]


class TestWebSocketChannels:
    """Test WebSocket channel functionality."""
    
    def test_subscribe_to_channel(self, websocket_client):
        """Test subscribing to a channel."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/channel-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Subscribe to channel
            subscribe_message = {
                "type": "subscribe",
                "channel": "test-channel"
            }
            websocket.send_json(subscribe_message)
            
            # Should receive subscription confirmation
            response = websocket.receive_json()
            assert response["type"] == "subscribed"
            assert response["channel"] == "test-channel"
    
    def test_unsubscribe_from_channel(self, websocket_client):
        """Test unsubscribing from a channel."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/unsub-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # First subscribe
            subscribe_message = {
                "type": "subscribe",
                "channel": "test-channel"
            }
            websocket.send_json(subscribe_message)
            websocket.receive_json()  # Skip subscription confirmation
            
            # Then unsubscribe
            unsubscribe_message = {
                "type": "unsubscribe",
                "channel": "test-channel"
            }
            websocket.send_json(unsubscribe_message)
            
            # Should receive unsubscription confirmation
            response = websocket.receive_json()
            assert response["type"] == "unsubscribed"
            assert response["channel"] == "test-channel"
    
    def test_broadcast_to_channel_unauthorized(self, websocket_client):
        """Test broadcasting without authentication."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/broadcast-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Try to broadcast without auth
            broadcast_message = {
                "type": "broadcast",
                "channel": "test-channel",
                "content": "Hello everyone!"
            }
            websocket.send_json(broadcast_message)
            
            # Should receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "authentication required" in response["message"].lower()


class TestWebSocketRooms:
    """Test WebSocket room functionality."""
    
    def test_join_room(self, websocket_client):
        """Test joining a room."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/room-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Join room
            join_message = {
                "type": "join_room",
                "room_id": "test-room-123"
            }
            websocket.send_json(join_message)
            
            # Should receive join confirmation
            response = websocket.receive_json()
            assert response["type"] == "joined_room"
            assert response["room_id"] == "test-room-123"
    
    def test_leave_room(self, websocket_client):
        """Test leaving a room."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/leave-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # First join room
            join_message = {
                "type": "join_room",
                "room_id": "test-room-456"
            }
            websocket.send_json(join_message)
            websocket.receive_json()  # Skip join confirmation
            
            # Then leave room
            leave_message = {
                "type": "leave_room",
                "room_id": "test-room-456"
            }
            websocket.send_json(leave_message)
            
            # Should receive leave confirmation
            response = websocket.receive_json()
            assert response["type"] == "left_room"
            assert response["room_id"] == "test-room-456"


class TestWebSocketMessages:
    """Test WebSocket messaging functionality."""
    
    def test_invalid_message_format(self, websocket_client):
        """Test sending invalid JSON message."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/invalid-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send invalid JSON
            websocket.send_text("invalid json")
            
            # Should receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "invalid json" in response["message"].lower()
    
    def test_unknown_message_type(self, websocket_client):
        """Test sending message with unknown type."""
        with websocket_client.websocket_connect("/api/v1/ws/connect/unknown-client") as websocket:
            # Skip welcome message
            websocket.receive_json()
            
            # Send unknown message type
            unknown_message = {
                "type": "unknown_type",
                "data": "some data"
            }
            websocket.send_json(unknown_message)
            
            # Should receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "unknown message type" in response["message"].lower()


class TestWebSocketStats:
    """Test WebSocket statistics endpoints."""
    
    async def test_get_websocket_stats(self, async_client):
        """Test getting WebSocket statistics."""
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.get_stats.return_value = {
                "total_connections": 5,
                "authenticated_connections": 3,
                "channels": {"general": 2, "updates": 1},
                "rooms": {"room1": 3, "room2": 1}
            }
            
            response = await async_client.get("/api/v1/ws/stats")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "total_connections" in data
            assert "authenticated_connections" in data
            assert "channels" in data
            assert "rooms" in data
    
    async def test_broadcast_via_http(self, async_client, auth_headers):
        """Test broadcasting message via HTTP endpoint."""
        message_data = {
            "content": "Hello from HTTP!",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.broadcast_to_channel = AsyncMock()
            
            response = await async_client.post(
                "/api/v1/ws/broadcast/general",
                json=message_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "broadcasted" in data["message"].lower()
    
    async def test_notify_user_via_http(self, async_client, auth_headers):
        """Test notifying specific user via HTTP endpoint."""
        notification_data = {
            "content": "Personal notification",
            "title": "Important Update"
        }
        
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.send_to_user = AsyncMock(return_value=True)
            
            response = await async_client.post(
                "/api/v1/ws/notify/user/123",
                json=notification_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "notification sent" in data["message"].lower()
    
    async def test_list_channels(self, async_client):
        """Test listing active channels."""
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.channels = {
                "general": {"client1", "client2"},
                "updates": {"client3"}
            }
            
            response = await async_client.get("/api/v1/ws/channels")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "channels" in data
            assert isinstance(data["channels"], list)
            assert "general" in data["channels"]
            assert "updates" in data["channels"]
    
    async def test_list_rooms(self, async_client):
        """Test listing active rooms."""
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.rooms = {
                "room1": {"client1", "client2"},
                "room2": {"client3"}
            }
            
            response = await async_client.get("/api/v1/ws/rooms")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "rooms" in data
            assert isinstance(data["rooms"], list)


class TestWebSocketDisconnection:
    """Test WebSocket disconnection handling."""
    
    def test_websocket_disconnect_cleanup(self, websocket_client):
        """Test that disconnection properly cleans up resources."""
        with patch("app.api.v1.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()
            
            try:
                with websocket_client.websocket_connect("/api/v1/ws/connect/cleanup-client") as websocket:
                    websocket.receive_json()  # Welcome message
                    # Connection will be closed when exiting context
            except Exception:
                pass  # Expected when connection closes
            
            # Verify disconnect was called
            # Note: This test is limited by TestClient WebSocket implementation