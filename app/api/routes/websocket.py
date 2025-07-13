"""WebSocket routes for real-time communication."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import Optional

from app.logger import logger
from app.websocket.handlers import WebSocketConnectionHandler
from app.websocket.manager import websocket_manager

router = APIRouter(prefix="/ws", tags=["websocket"])

# WebSocket connection handler
ws_handler = WebSocketConnectionHandler()


@router.websocket("/conversations/{conversation_id}")
async def websocket_conversation(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time conversation communication.

    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID
        token: Authentication token
    """
    try:
        logger.info(f"WebSocket connection attempt for conversation {conversation_id}")
        await ws_handler.handle_connection(websocket, conversation_id, token)
    except Exception as e:
        logger.error(f"WebSocket route error: {e}")
        logger.exception("Full WebSocket route error traceback:")
        try:
            await websocket.close(code=1011, reason="Server error")
        except:
            pass


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics.

    Returns:
        dict: WebSocket statistics
    """
    return {
        "websocket_stats": websocket_manager.get_stats(),
        "active_conversations": list(websocket_manager.connections.keys()),
        "active_users": list(websocket_manager.user_connections.keys())
    }


@router.post("/broadcast/{conversation_id}")
async def broadcast_to_conversation(
    conversation_id: str,
    message: dict
):
    """Broadcast a message to all connections in a conversation.

    Args:
        conversation_id: Conversation ID
        message: Message to broadcast

    Returns:
        dict: Broadcast result
    """
    try:
        sent_count = await websocket_manager.send_to_conversation(conversation_id, message)
        return {
            "success": True,
            "sent_to": sent_count,
            "conversation_id": conversation_id
        }
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail="Broadcast failed")
