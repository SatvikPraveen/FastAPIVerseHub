# File: app/api/v1/websocket.py

import json
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.security import security_manager
from app.services.notification_service import NotificationService, ConnectionManager

router = APIRouter()
logger = logging.getLogger(__name__)

# Global connection manager
connection_manager = ConnectionManager()


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[int]:
    """Get current user from WebSocket token."""
    if not token:
        return None
    
    try:
        payload = security_manager.verify_access_token(token)
        user_id = int(payload.get("sub"))
        
        # Verify user exists and is active
        from app.services.user_service import UserService
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        
        if user and user.is_active:
            return user_id
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
    
    return None


@router.websocket("/connect/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket connection endpoint."""
    await websocket.accept()
    
    user_id = None
    if token:
        user_id = await get_current_user_ws(websocket, token, db)
    
    try:
        # Add connection to manager
        await connection_manager.connect(websocket, client_id, user_id)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected successfully",
            "client_id": client_id,
            "authenticated": user_id is not None
        })
        
        # Listen for messages
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, client_id, user_id, message, db)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal server error"
                })
    
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
        logger.info(f"WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(client_id)


async def handle_websocket_message(
    websocket: WebSocket,
    client_id: str,
    user_id: Optional[int],
    message: Dict,
    db: AsyncSession
):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    
    if message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "timestamp": message.get("timestamp")
        })
    
    elif message_type == "subscribe":
        channel = message.get("channel")
        if channel:
            await connection_manager.subscribe_to_channel(client_id, channel)
            await websocket.send_json({
                "type": "subscribed",
                "channel": channel,
                "message": f"Subscribed to {channel}"
            })
    
    elif message_type == "unsubscribe":
        channel = message.get("channel")
        if channel:
            await connection_manager.unsubscribe_from_channel(client_id, channel)
            await websocket.send_json({
                "type": "unsubscribed",
                "channel": channel,
                "message": f"Unsubscribed from {channel}"
            })
    
    elif message_type == "broadcast":
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required for broadcasting"
            })
            return
        
        channel = message.get("channel", "general")
        content = message.get("content", "")
        
        broadcast_message = {
            "type": "broadcast",
            "channel": channel,
            "user_id": user_id,
            "content": content,
            "timestamp": message.get("timestamp")
        }
        
        await connection_manager.broadcast_to_channel(channel, broadcast_message)
    
    elif message_type == "private_message":
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required for private messages"
            })
            return
        
        target_user_id = message.get("target_user_id")
        content = message.get("content", "")
        
        if target_user_id:
            private_message = {
                "type": "private_message",
                "from_user_id": user_id,
                "content": content,
                "timestamp": message.get("timestamp")
            }
            
            sent = await connection_manager.send_to_user(target_user_id, private_message)
            
            if sent:
                await websocket.send_json({
                    "type": "message_sent",
                    "message": "Private message sent successfully"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Target user not connected"
                })
    
    elif message_type == "join_room":
        room_id = message.get("room_id")
        if room_id:
            await connection_manager.join_room(client_id, room_id)
            await websocket.send_json({
                "type": "joined_room",
                "room_id": room_id,
                "message": f"Joined room {room_id}"
            })
    
    elif message_type == "leave_room":
        room_id = message.get("room_id")
        if room_id:
            await connection_manager.leave_room(client_id, room_id)
            await websocket.send_json({
                "type": "left_room",
                "room_id": room_id,
                "message": f"Left room {room_id}"
            })
    
    elif message_type == "room_message":
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required for room messages"
            })
            return
        
        room_id = message.get("room_id")
        content = message.get("content", "")
        
        if room_id:
            room_message = {
                "type": "room_message",
                "room_id": room_id,
                "user_id": user_id,
                "content": content,
                "timestamp": message.get("timestamp")
            }
            
            await connection_manager.broadcast_to_room(room_id, room_message)
    
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        })


@router.get("/stats")
async def get_websocket_stats() -> Dict:
    """Get WebSocket connection statistics."""
    stats = connection_manager.get_stats()
    return {
        "total_connections": stats["total_connections"],
        "authenticated_connections": stats["authenticated_connections"],
        "channels": stats["channels"],
        "rooms": stats["rooms"]
    }


@router.post("/broadcast/{channel}")
async def broadcast_message(
    channel: str,
    message: Dict,
    current_user = Depends(get_current_user),
) -> Dict[str, str]:
    """Broadcast message to a channel via HTTP."""
    broadcast_data = {
        "type": "broadcast",
        "channel": channel,
        "user_id": current_user.id,
        "content": message.get("content", ""),
        "timestamp": message.get("timestamp")
    }
    
    await connection_manager.broadcast_to_channel(channel, broadcast_data)
    
    return {"message": f"Message broadcasted to channel {channel}"}


@router.post("/notify/user/{user_id}")
async def notify_user(
    user_id: int,
    message: Dict,
    current_user = Depends(get_current_user),
) -> Dict[str, str]:
    """Send notification to specific user via HTTP."""
    notification_data = {
        "type": "notification",
        "from_user_id": current_user.id,
        "content": message.get("content", ""),
        "title": message.get("title", "New Notification"),
        "timestamp": message.get("timestamp")
    }
    
    sent = await connection_manager.send_to_user(user_id, notification_data)
    
    if sent:
        return {"message": f"Notification sent to user {user_id}"}
    else:
        return {"message": f"User {user_id} is not connected"}


@router.get("/channels")
async def list_channels() -> Dict[str, List[str]]:
    """List all active channels."""
    return {"channels": list(connection_manager.channels.keys())}


@router.get("/rooms")
async def list_rooms() -> Dict[str, List[str]]:
    """List all active rooms."""
    return {"rooms": list(connection_manager.rooms.keys())}