"""WebSocket connection manager for real-time communication."""

import json
import asyncio
from typing import Dict, List, Optional, Set, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from app.logger import logger


class WebSocketConnection:
    """Represents a WebSocket connection with metadata."""
    
    def __init__(self, websocket: WebSocket, user_id: str, conversation_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the WebSocket client.
        
        Args:
            message: Message to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            await self.websocket.send_text(json.dumps(message))
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False
    
    async def close(self, code: int = 1000, reason: str = "Connection closed"):
        """Close the WebSocket connection.
        
        Args:
            code: Close code
            reason: Close reason
        """
        try:
            await self.websocket.close(code=code, reason=reason)
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")


class WebSocketManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        # Active connections by conversation ID
        self.connections: Dict[str, List[WebSocketConnection]] = {}
        
        # Connection lookup by user ID
        self.user_connections: Dict[str, List[WebSocketConnection]] = {}
        
        # All active connections
        self.active_connections: Set[WebSocketConnection] = set()
    
    async def connect(self, websocket: WebSocket, user_id: str, conversation_id: str) -> WebSocketConnection:
        """Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            user_id: User ID
            conversation_id: Conversation ID
            
        Returns:
            WebSocketConnection: The created connection
        """
        await websocket.accept()
        
        connection = WebSocketConnection(websocket, user_id, conversation_id)
        
        # Add to conversation connections
        if conversation_id not in self.connections:
            self.connections[conversation_id] = []
        self.connections[conversation_id].append(connection)
        
        # Add to user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection)
        
        # Add to active connections
        self.active_connections.add(connection)
        
        logger.info(f"WebSocket connected: user {user_id}, conversation {conversation_id}")
        
        # Send connection confirmation
        await connection.send_message({
            "type": "connection.established",
            "data": {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "connected_at": connection.connected_at.isoformat()
            }
        })
        
        return connection
    
    async def disconnect(self, connection: WebSocketConnection):
        """Disconnect a WebSocket connection.
        
        Args:
            connection: Connection to disconnect
        """
        try:
            # Remove from conversation connections
            if connection.conversation_id in self.connections:
                if connection in self.connections[connection.conversation_id]:
                    self.connections[connection.conversation_id].remove(connection)
                
                # Clean up empty conversation lists
                if not self.connections[connection.conversation_id]:
                    del self.connections[connection.conversation_id]
            
            # Remove from user connections
            if connection.user_id in self.user_connections:
                if connection in self.user_connections[connection.user_id]:
                    self.user_connections[connection.user_id].remove(connection)
                
                # Clean up empty user lists
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]
            
            # Remove from active connections
            self.active_connections.discard(connection)
            
            logger.info(f"WebSocket disconnected: user {connection.user_id}, conversation {connection.conversation_id}")
            
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")
    
    async def send_to_conversation(self, conversation_id: str, message: Dict[str, Any]) -> int:
        """Send a message to all connections in a conversation.
        
        Args:
            conversation_id: Conversation ID
            message: Message to send
            
        Returns:
            int: Number of successful sends
        """
        if conversation_id not in self.connections:
            return 0
        
        connections = self.connections[conversation_id].copy()
        successful_sends = 0
        failed_connections = []
        
        for connection in connections:
            success = await connection.send_message(message)
            if success:
                successful_sends += 1
            else:
                failed_connections.append(connection)
        
        # Clean up failed connections
        for failed_connection in failed_connections:
            await self.disconnect(failed_connection)
        
        return successful_sends
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Send a message to all connections for a user.
        
        Args:
            user_id: User ID
            message: Message to send
            
        Returns:
            int: Number of successful sends
        """
        if user_id not in self.user_connections:
            return 0
        
        connections = self.user_connections[user_id].copy()
        successful_sends = 0
        failed_connections = []
        
        for connection in connections:
            success = await connection.send_message(message)
            if success:
                successful_sends += 1
            else:
                failed_connections.append(connection)
        
        # Clean up failed connections
        for failed_connection in failed_connections:
            await self.disconnect(failed_connection)
        
        return successful_sends
    
    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast a message to all active connections.
        
        Args:
            message: Message to broadcast
            
        Returns:
            int: Number of successful sends
        """
        connections = list(self.active_connections)
        successful_sends = 0
        failed_connections = []
        
        for connection in connections:
            success = await connection.send_message(message)
            if success:
                successful_sends += 1
            else:
                failed_connections.append(connection)
        
        # Clean up failed connections
        for failed_connection in failed_connections:
            await self.disconnect(failed_connection)
        
        return successful_sends
    
    def get_conversation_connections(self, conversation_id: str) -> List[WebSocketConnection]:
        """Get all connections for a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List[WebSocketConnection]: List of connections
        """
        return self.connections.get(conversation_id, [])
    
    def get_user_connections(self, user_id: str) -> List[WebSocketConnection]:
        """Get all connections for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List[WebSocketConnection]: List of connections
        """
        return self.user_connections.get(user_id, [])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics.
        
        Returns:
            Dict[str, Any]: Statistics
        """
        return {
            "total_connections": len(self.active_connections),
            "conversations_with_connections": len(self.connections),
            "users_with_connections": len(self.user_connections),
            "connections_by_conversation": {
                conv_id: len(conns) for conv_id, conns in self.connections.items()
            }
        }


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
