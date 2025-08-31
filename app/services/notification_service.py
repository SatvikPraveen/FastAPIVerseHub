# File: app/services/notification_service.py

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message routing."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, Set[str]] = defaultdict(set)
        self.channels: Dict[str, Set[str]] = defaultdict(set)
        self.rooms: Dict[str, Set[str]] = defaultdict(set)
        self.client_users: Dict[str, Optional[int]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[int] = None):
        """Connect a new WebSocket client."""
        self.active_connections[client_id] = websocket
        self.client_users[client_id] = user_id
        
        if user_id:
            self.user_connections[user_id].add(client_id)
        
        logger.info(f"Client {client_id} connected (user_id: {user_id})")
    
    def disconnect(self, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        user_id = self.client_users.get(client_id)
        if user_id and client_id in self.user_connections[user_id]:
            self.user_connections[user_id].remove(client_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        if client_id in self.client_users:
            del self.client_users[client_id]
        
        # Remove from all channels and rooms
        for channel_clients in self.channels.values():
            channel_clients.discard(client_id)
        
        for room_clients in self.rooms.values():
            room_clients.discard(client_id)
        
        logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, message: str, client_id: str) -> bool:
        """Send message to specific client."""
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
        return False
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """Send message to all connections of a specific user."""
        client_ids = self.user_connections.get(user_id, set())
        if not client_ids:
            return False
        
        message_str = json.dumps(message)
        sent_count = 0
        
        for client_id in client_ids.copy():
            if await self.send_personal_message(message_str, client_id):
                sent_count += 1
        
        return sent_count > 0
    
    async def subscribe_to_channel(self, client_id: str, channel: str):
        """Subscribe client to a channel."""
        self.channels[channel].add(client_id)
        logger.info(f"Client {client_id} subscribed to channel {channel}")
    
    async def unsubscribe_from_channel(self, client_id: str, channel: str):
        """Unsubscribe client from a channel."""
        self.channels[channel].discard(client_id)
        logger.info(f"Client {client_id} unsubscribed from channel {channel}")
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all clients in a channel."""
        client_ids = self.channels.get(channel, set()).copy()
        if not client_ids:
            return
        
        message_str = json.dumps(message)
        
        for client_id in client_ids:
            await self.send_personal_message(message_str, client_id)
    
    async def join_room(self, client_id: str, room_id: str):
        """Join client to a room."""
        self.rooms[room_id].add(client_id)
        logger.info(f"Client {client_id} joined room {room_id}")
    
    async def leave_room(self, client_id: str, room_id: str):
        """Remove client from a room."""
        self.rooms[room_id].discard(client_id)
        logger.info(f"Client {client_id} left room {room_id}")
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any]):
        """Broadcast message to all clients in a room."""
        client_ids = self.rooms.get(room_id, set()).copy()
        if not client_ids:
            return
        
        message_str = json.dumps(message)
        
        for client_id in client_ids:
            await self.send_personal_message(message_str, client_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        authenticated_count = sum(1 for user_id in self.client_users.values() if user_id)
        
        return {
            "total_connections": len(self.active_connections),
            "authenticated_connections": authenticated_count,
            "channels": {channel: len(clients) for channel, clients in self.channels.items()},
            "rooms": {room: len(clients) for room, clients in self.rooms.items()}
        }


class SSEManager:
    """Manages Server-Sent Events connections and message routing."""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.user_clients: Dict[int, Set[str]] = defaultdict(set)
        self.channel_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.message_queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.stats = {
            "total_messages_sent": 0,
            "start_time": datetime.utcnow()
        }
    
    async def subscribe_to_channel(self, client_id: str, channel: str, user_id: Optional[int] = None):
        """Subscribe client to SSE channel."""
        self.channel_subscribers[channel].add(client_id)
        
        if client_id not in self.clients:
            self.clients[client_id] = {
                "user_id": user_id,
                "channels": set(),
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow()
            }
        
        self.clients[client_id]["channels"].add(channel)
        
        if user_id:
            self.user_clients[user_id].add(client_id)
        
        logger.info(f"SSE client {client_id} subscribed to channel {channel}")
    
    async def subscribe_to_user_events(self, client_id: str, user_id: int):
        """Subscribe client to user-specific events."""
        await self.subscribe_to_channel(client_id, f"user_{user_id}", user_id)
    
    async def publish_to_channel(self, channel: str, message: Dict[str, Any]) -> int:
        """Publish message to all subscribers of a channel."""
        subscribers = self.channel_subscribers.get(channel, set()).copy()
        
        for client_id in subscribers:
            self.message_queues[client_id].append(message)
        
        self.stats["total_messages_sent"] += len(subscribers)
        return len(subscribers)
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """Send message to specific user via SSE."""
        client_ids = self.user_clients.get(user_id, set())
        if not client_ids:
            return False
        
        for client_id in client_ids:
            self.message_queues[client_id].append(message)
        
        self.stats["total_messages_sent"] += len(client_ids)
        return True
    
    async def get_messages_for_client(self, client_id: str) -> List[Dict[str, Any]]:
        """Get pending messages for a client."""
        messages = self.message_queues.get(client_id, []).copy()
        self.message_queues[client_id] = []  # Clear after retrieval
        
        if client_id in self.clients:
            self.clients[client_id]["last_activity"] = datetime.utcnow()
        
        return messages
    
    async def remove_client(self, client_id: str):
        """Remove client from SSE manager."""
        if client_id in self.clients:
            user_id = self.clients[client_id].get("user_id")
            channels = self.clients[client_id].get("channels", set())
            
            # Remove from channels
            for channel in channels:
                self.channel_subscribers[channel].discard(client_id)
            
            # Remove from user clients
            if user_id:
                self.user_clients[user_id].discard(client_id)
                if not self.user_clients[user_id]:
                    del self.user_clients[user_id]
            
            del self.clients[client_id]
        
        # Clear message queue
        if client_id in self.message_queues:
            del self.message_queues[client_id]
        
        logger.info(f"SSE client {client_id} removed")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get SSE statistics."""
        uptime = (datetime.utcnow() - self.stats["start_time"]).total_seconds()
        
        return {
            "total_clients": len(self.clients),
            "authenticated_clients": sum(1 for client in self.clients.values() if client.get("user_id")),
            "active_channels": len([ch for ch, subs in self.channel_subscribers.items() if subs]),
            "total_messages_sent": self.stats["total_messages_sent"],
            "uptime_seconds": uptime
        }
    
    async def get_active_channels(self) -> List[Dict[str, Any]]:
        """Get list of active channels with metadata."""
        channels = []
        
        for channel, subscribers in self.channel_subscribers.items():
            if subscribers:  # Only active channels
                channels.append({
                    "name": channel,
                    "subscriber_count": len(subscribers),
                    "last_message_at": datetime.utcnow()  # Placeholder
                })
        
        return channels
    
    async def clear_channel(self, channel: str) -> int:
        """Clear all messages from a channel."""
        subscribers = self.channel_subscribers.get(channel, set())
        cleared_count = 0
        
        for client_id in subscribers:
            if client_id in self.message_queues:
                # Remove messages for this channel (simplified)
                cleared_count += len(self.message_queues[client_id])
                self.message_queues[client_id] = []
        
        return cleared_count


class NotificationService:
    """High-level notification service combining WebSocket and SSE."""
    
    def __init__(self):
        self.websocket_manager = ConnectionManager()
        self.sse_manager = SSEManager()
    
    async def send_notification(
        self,
        user_id: int,
        notification: Dict[str, Any],
        channels: Optional[List[str]] = None
    ) -> bool:
        """Send notification via all available channels."""
        sent_websocket = await self.websocket_manager.send_to_user(user_id, notification)
        sent_sse = await self.sse_manager.send_to_user(user_id, notification)
        
        # Also broadcast to specific channels if provided
        if channels:
            for channel in channels:
                await self.websocket_manager.broadcast_to_channel(channel, notification)
                await self.sse_manager.publish_to_channel(channel, notification)
        
        return sent_websocket or sent_sse
    
    async def broadcast_announcement(
        self,
        message: str,
        title: str = "Announcement",
        channels: Optional[List[str]] = None
    ):
        """Broadcast system announcement to all users."""
        announcement = {
            "type": "announcement",
            "title": title,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "priority": "normal"
        }
        
        target_channels = channels or ["general", "announcements"]
        
        for channel in target_channels:
            await self.websocket_manager.broadcast_to_channel(channel, announcement)
            await self.sse_manager.publish_to_channel(channel, announcement)
    
    async def send_course_update(
        self,
        course_id: int,
        update_type: str,
        message: str,
        enrolled_users: List[int]
    ):
        """Send course update notification to enrolled users."""
        notification = {
            "type": "course_update",
            "course_id": course_id,
            "update_type": update_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for user_id in enrolled_users:
            await self.send_notification(user_id, notification)
    
    async def send_achievement_notification(
        self,
        user_id: int,
        achievement: Dict[str, Any]
    ):
        """Send achievement notification to user."""
        notification = {
            "type": "achievement",
            "title": "Achievement Unlocked!",
            "achievement": achievement,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_notification(user_id, notification, ["achievements"])