"""WebSocket event handlers for real-time communication."""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.logger import logger
from app.websocket.manager import WebSocketConnection, websocket_manager
from app.event.base import BaseEventHandler
from app.event.manager import event_manager
from app.services.conversation_service import ConversationService
from app.services.auth_service import AuthService


class ConversationWebSocketHandler(BaseEventHandler):
    """WebSocket handler for conversation events."""

    name: str = "websocket_conversation_handler"
    description: str = "Handles conversation events for WebSocket clients"
    enabled: bool = True
    priority: int = 200
    supported_events: list = [
        "conversation.userinput",
        "conversation.agentresponse",
        "conversation.llmstream",
        "conversation.toolresultdisplay",
        "conversation.interrupted",
        "agent.agentstepstart",
        "agent.agentstepcomplete",
        "tool.toolexecution",
        "system.systemerror"
    ]

    async def handle(self, event) -> bool:
        """Handle event by broadcasting to WebSocket clients.

        Args:
            event: The event to handle

        Returns:
            bool: True if handling was successful
        """
        try:
            # Only handle events with conversation_id
            if not hasattr(event, 'conversation_id') or not event.conversation_id:
                return True

            # Create WebSocket message based on event type
            message = await self._create_websocket_message(event)
            if not message:
                return True

            # Send to all connections in the conversation
            sent_count = await websocket_manager.send_to_conversation(
                event.conversation_id,
                message
            )

            if sent_count > 0:
                logger.debug(f"Sent WebSocket message to {sent_count} clients for event {event.event_id}")

            return True

        except Exception as e:
            logger.error(f"WebSocket handler error for event {event.event_id}: {e}")
            return False

    async def _create_websocket_message(self, event) -> Optional[Dict[str, Any]]:
        """Create WebSocket message from event.

        Args:
            event: The event to convert

        Returns:
            Optional[Dict[str, Any]]: WebSocket message or None
        """
        base_message = {
            "type": event.event_type,
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "conversation_id": getattr(event, 'conversation_id', None),
            "data": event.data
        }

        # Customize message based on event type
        if event.event_type == "conversation.userinput":
            return {
                **base_message,
                "type": "message.user",
                "content": event.data.get("message", ""),
                "role": "user"
            }

        elif event.event_type == "conversation.agentresponse":
            return {
                **base_message,
                "type": "message.assistant",
                "content": event.data.get("response", ""),
                "role": "assistant"
            }

        elif event.event_type == "conversation.llmstream":
            return {
                **base_message,
                "type": "llm.stream",
                "content": event.data.get("content", ""),
                "is_complete": event.data.get("is_complete", False),
                "agent_name": event.data.get("agent_name", ""),
                "agent_type": event.data.get("agent_type", "")
            }

        elif event.event_type == "conversation.toolresultdisplay":
            return {
                **base_message,
                "type": "tool.result",
                "tool_name": event.data.get("tool_name", ""),
                "result": event.data.get("result", ""),
                "truncated": event.data.get("truncated", False)
            }

        elif event.event_type == "agent.agentstepstart":
            return {
                **base_message,
                "type": "agent.step_start",
                "step": event.data.get("step_number", 0),
                "total_steps": event.data.get("total_steps", 20),
                "agent": event.data.get("agent_name", "unknown"),
                "description": f"Executing step {event.data.get('step_number', 0)}/{event.data.get('total_steps', 20)}"
            }

        elif event.event_type == "agent.agentstepcomplete":
            return {
                **base_message,
                "type": "agent.step_complete",
                "step": event.data.get("step_number", 0),
                "total_steps": event.data.get("total_steps", 20),
                "result": event.data.get("result", ""),
                "thoughts": event.data.get("thoughts", ""),
                "tools_selected": event.data.get("tools_selected", []),
                "tool_count": event.data.get("tool_count", 0),
                "description": f"Step {event.data.get('step_number', 0)} completed"
            }

        elif event.event_type == "tool.toolexecution":
            return {
                **base_message,
                "type": "tool.execution",
                "tool_name": event.data.get("tool_name", ""),
                "status": event.data.get("status", ""),
                "parameters": event.data.get("parameters", {})
            }

        elif event.event_type == "conversation.interrupted":
            return {
                **base_message,
                "type": "conversation.interrupted",
                "reason": event.data.get("reason", "user_interrupt")
            }

        elif event.event_type == "system.systemerror":
            return {
                **base_message,
                "type": "error",
                "error_type": event.data.get("error_type", "unknown"),
                "error_message": event.data.get("error_message", "")
            }

        # Default message for other event types
        return base_message


class WebSocketConnectionHandler:
    """Handles individual WebSocket connections."""

    def __init__(self):
        self.auth_service = None
        self.conversation_service = None

    async def handle_connection(self, websocket: WebSocket, conversation_id: str, token: str):
        """Handle a WebSocket connection for a conversation.

        Args:
            websocket: WebSocket instance
            conversation_id: Conversation ID
            token: Authentication token
        """
        from app.api.dependencies import get_database
        from app.services.auth_service import AuthService
        from app.services.conversation_service import ConversationService

        connection = None

        try:
            # Initialize services with database session
            async for session in get_database():
                self.auth_service = AuthService()
                self.conversation_service = ConversationService(session)

                # Authenticate user
                user = await self.auth_service.get_current_user(token)
                if not user:
                    await websocket.close(code=4001, reason="Authentication failed")
                    return

                # Verify user has access to conversation
                conversation = await self.conversation_service.get_conversation(conversation_id)
                if not conversation or conversation.user_id != user.id:
                    await websocket.close(code=4003, reason="Access denied")
                    return

                # Accept connection
                connection = await websocket_manager.connect(websocket, user.id, conversation_id)

                # Handle incoming messages
                await self._handle_messages(connection)
                break  # Exit the async for loop

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"WebSocket connection error for conversation {conversation_id}: {e}")
            logger.exception("Full WebSocket error traceback:")
            try:
                await websocket.close(code=1011, reason="Server error")
            except:
                pass
        finally:
            if connection:
                await websocket_manager.disconnect(connection)

    async def _handle_messages(self, connection: WebSocketConnection):
        """Handle incoming WebSocket messages.

        Args:
            connection: WebSocket connection
        """
        while True:
            try:
                # Receive message
                data = await connection.websocket.receive_text()
                message = json.loads(data)

                # Process message based on type
                await self._process_message(connection, message)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await connection.send_message({
                    "type": "error",
                    "error": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await connection.send_message({
                    "type": "error",
                    "error": "Message processing failed"
                })

    async def _process_message(self, connection: WebSocketConnection, message: Dict[str, Any]):
        """Process an incoming WebSocket message.

        Args:
            connection: WebSocket connection
            message: Received message
        """
        message_type = message.get("type")

        if message_type == "ping":
            # Respond to ping with pong
            await connection.send_message({"type": "pong"})

        elif message_type == "send_message":
            # Send a message in the conversation
            content = message.get("content", "")
            if content.strip():
                event_id = await self.conversation_service.send_message(
                    conversation_id=connection.conversation_id,
                    user_id=connection.user_id,
                    message=content
                )

                if event_id:
                    await connection.send_message({
                        "type": "message_sent",
                        "event_id": event_id
                    })
                else:
                    await connection.send_message({
                        "type": "error",
                        "error": "Failed to send message"
                    })

        elif message_type == "interrupt":
            # Interrupt the conversation
            success = await self.conversation_service.interrupt_conversation(
                conversation_id=connection.conversation_id,
                user_id=connection.user_id
            )

            await connection.send_message({
                "type": "interrupt_result",
                "success": success
            })

        elif message_type == "get_history":
            # Get conversation history
            limit = message.get("limit", 50)
            offset = message.get("offset", 0)

            history = await self.conversation_service.get_conversation_history(
                conversation_id=connection.conversation_id,
                user_id=connection.user_id,
                limit=limit,
                offset=offset
            )

            await connection.send_message({
                "type": "history",
                "messages": history
            })

        else:
            await connection.send_message({
                "type": "error",
                "error": f"Unknown message type: {message_type}"
            })
