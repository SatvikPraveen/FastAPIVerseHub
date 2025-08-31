# File: app/api/v1/sse.py

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_current_user_optional, get_db
from app.models.user import User
from app.services.notification_service import SSEManager

router = APIRouter()
logger = logging.getLogger(__name__)

# Global SSE manager
sse_manager = SSEManager()


async def event_stream(
    user_id: Optional[int] = None,
    channels: Optional[str] = None,
    last_event_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events stream."""
    client_id = f"sse_{user_id}_{datetime.utcnow().timestamp()}"
    
    # Parse channels
    channel_list = []
    if channels:
        channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
    
    # Subscribe to channels
    for channel in channel_list:
        await sse_manager.subscribe_to_channel(client_id, channel, user_id)
    
    # Subscribe to user-specific events if authenticated
    if user_id:
        await sse_manager.subscribe_to_user_events(client_id, user_id)
    
    try:
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'message': 'Connected to SSE stream', 'client_id': client_id, 'channels': channel_list})}\n\n"
        
        # Send heartbeat every 30 seconds and check for messages
        last_heartbeat = datetime.utcnow()
        
        while True:
            current_time = datetime.utcnow()
            
            # Check for new messages
            messages = await sse_manager.get_messages_for_client(client_id)
            
            for message in messages:
                event_data = {
                    "id": message.get("id", ""),
                    "type": message.get("type", "message"),
                    "data": message.get("data", {}),
                    "timestamp": message.get("timestamp", current_time.isoformat())
                }
                
                yield f"id: {event_data['id']}\nevent: {event_data['type']}\ndata: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds
            if (current_time - last_heartbeat).seconds >= 30:
                heartbeat_data = {
                    "type": "heartbeat",
                    "timestamp": current_time.isoformat(),
                    "client_id": client_id
                }
                yield f"event: heartbeat\ndata: {json.dumps(heartbeat_data)}\n\n"
                last_heartbeat = current_time
            
            # Wait before next check
            await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for client {client_id}")
    except Exception as e:
        logger.error(f"SSE stream error for client {client_id}: {e}")
        error_data = {
            "type": "error",
            "message": "Stream error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
    
    finally:
        # Clean up subscriptions
        await sse_manager.remove_client(client_id)


@router.get("/events")
async def sse_endpoint(
    request: Request,
    channels: Optional[str] = Query(None, description="Comma-separated list of channels to subscribe to"),
    last_event_id: Optional[str] = Query(None, description="Last event ID for resuming stream"),
    current_user: Optional[User] = Depends(get_current_user_optional())
) -> EventSourceResponse:
    """Server-Sent Events endpoint."""
    user_id = current_user.id if current_user else None
    
    return EventSourceResponse(
        event_stream(user_id, channels, last_event_id),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.post("/publish/{channel}")
async def publish_to_channel(
    channel: str,
    message: dict,
    current_user: User = Depends(get_current_user_optional()),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Publish message to SSE channel."""
    event_data = {
        "id": f"msg_{datetime.utcnow().timestamp()}",
        "type": message.get("type", "message"),
        "channel": channel,
        "data": {
            "content": message.get("content", ""),
            "title": message.get("title", ""),
            "user_id": current_user.id if current_user else None,
            "metadata": message.get("metadata", {})
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await sse_manager.publish_to_channel(channel, event_data)
    
    return {
        "message": f"Published to channel {channel}",
        "event_id": event_data["id"]
    }


@router.post("/notify/user/{user_id}")
async def notify_user_sse(
    user_id: int,
    notification: dict,
    current_user: User = Depends(get_current_user_optional()),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Send notification to specific user via SSE."""
    event_data = {
        "id": f"notif_{datetime.utcnow().timestamp()}",
        "type": "notification",
        "data": {
            "title": notification.get("title", "New Notification"),
            "content": notification.get("content", ""),
            "from_user_id": current_user.id if current_user else None,
            "priority": notification.get("priority", "normal"),
            "action_url": notification.get("action_url"),
            "metadata": notification.get("metadata", {})
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    sent = await sse_manager.send_to_user(user_id, event_data)
    
    return {
        "message": f"Notification sent to user {user_id}" if sent else f"User {user_id} not subscribed",
        "event_id": event_data["id"],
        "delivered": sent
    }


@router.post("/broadcast")
async def broadcast_message(
    message: dict,
    channels: Optional[str] = Query(None, description="Comma-separated list of channels"),
    current_user: User = Depends(get_current_user_optional())
) -> dict:
    """Broadcast message to multiple channels."""
    event_data = {
        "id": f"broadcast_{datetime.utcnow().timestamp()}",
        "type": "broadcast",
        "data": {
            "title": message.get("title", "Broadcast Message"),
            "content": message.get("content", ""),
            "from_user_id": current_user.id if current_user else None,
            "metadata": message.get("metadata", {})
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    channel_list = []
    if channels:
        channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
    else:
        channel_list = ["general"]  # Default channel
    
    total_sent = 0
    for channel in channel_list:
        sent = await sse_manager.publish_to_channel(channel, event_data)
        total_sent += sent
    
    return {
        "message": f"Broadcasted to {len(channel_list)} channels",
        "channels": channel_list,
        "total_recipients": total_sent,
        "event_id": event_data["id"]
    }


@router.get("/stats")
async def get_sse_stats() -> dict:
    """Get SSE connection statistics."""
    stats = await sse_manager.get_stats()
    
    return {
        "total_clients": stats["total_clients"],
        "authenticated_clients": stats["authenticated_clients"],
        "active_channels": stats["active_channels"],
        "total_messages_sent": stats["total_messages_sent"],
        "uptime_seconds": stats["uptime_seconds"]
    }


@router.get("/channels")
async def list_active_channels() -> dict:
    """List all active SSE channels."""
    channels = await sse_manager.get_active_channels()
    
    return {
        "channels": [
            {
                "name": channel["name"],
                "subscriber_count": channel["subscriber_count"],
                "last_message_at": channel["last_message_at"]
            }
            for channel in channels
        ]
    }


@router.delete("/channels/{channel}")
async def clear_channel(
    channel: str,
    current_user: User = Depends(get_current_user_optional())
) -> dict:
    """Clear all messages from a channel (admin only)."""
    # In a real application, you might want to add admin-only permission check
    
    cleared = await sse_manager.clear_channel(channel)
    
    return {
        "message": f"Cleared channel {channel}",
        "messages_cleared": cleared
    }


@router.post("/test/events")
async def send_test_events(
    channel: str = "test",
    count: int = Query(5, ge=1, le=50),
    interval: float = Query(1.0, ge=0.1, le=10.0)
) -> dict:
    """Send test events to a channel (for testing purposes)."""
    event_ids = []
    
    for i in range(count):
        event_data = {
            "id": f"test_{datetime.utcnow().timestamp()}_{i}",
            "type": "test",
            "data": {
                "title": f"Test Event {i + 1}",
                "content": f"This is test event number {i + 1} of {count}",
                "sequence": i + 1,
                "total": count
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await sse_manager.publish_to_channel(channel, event_data)
        event_ids.append(event_data["id"])
        
        if i < count - 1:  # Don't wait after the last event
            await asyncio.sleep(interval)
    
    return {
        "message": f"Sent {count} test events to channel {channel}",
        "event_ids": event_ids,
        "channel": channel
    }