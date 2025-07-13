"""Event handler for agent integration."""

import asyncio
from typing import Set
from app.logger import logger
from app.event.base import BaseEventHandler
from app.services.agent_service import AgentService


class AgentEventHandler(BaseEventHandler):
    """Event handler that processes user messages with agents."""

    name: str = "agent_event_handler"
    description: str = "Processes user input events with AI agents"
    enabled: bool = True
    priority: int = 300  # Lower priority to run after persistence
    supported_events: list = ["conversation.userinput"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_service = AgentService()
        self._processing_conversations: Set[str] = set()

    async def handle(self, event) -> bool:
        """Handle user input events by processing with agent.

        Args:
            event: The user input event to handle

        Returns:
            bool: True if handling was successful
        """
        try:
            if event.event_type != "conversation.userinput":
                return True

            conversation_id = getattr(event, 'conversation_id', None)
            user_id = getattr(event, 'user_id', None)

            if not conversation_id or not user_id:
                logger.warning(f"User input event missing conversation_id or user_id: {event.event_id}")
                return True

            # Avoid concurrent processing for the same conversation
            if conversation_id in self._processing_conversations:
                logger.info(f"Conversation {conversation_id} already being processed, skipping")
                return True

            message = event.data.get("message", "")
            if not message.strip():
                logger.debug(f"Empty message in user input event: {event.event_id}")
                return True

            # Mark conversation as being processed
            self._processing_conversations.add(conversation_id)

            # Process message with agent in background task
            asyncio.create_task(
                self._process_with_agent(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message=message,
                    event_id=event.event_id
                )
            )

            logger.debug(f"Started agent processing for user input event: {event.event_id}")
            return True

        except Exception as e:
            logger.error(f"Error in agent event handler for event {event.event_id}: {e}")
            return False

    async def _process_with_agent(self, conversation_id: str, user_id: str,
                                message: str, event_id: str):
        """Process user message with agent.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            message: User message
            event_id: Event ID of the user input
        """
        try:
            success = await self.agent_service.process_user_message(
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
                event_id=event_id
            )

            if success:
                logger.info(f"Agent processing completed for conversation {conversation_id}")
            else:
                logger.warning(f"Agent processing failed for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Agent processing error for conversation {conversation_id}: {e}")
        finally:
            # Remove from processing set
            self._processing_conversations.discard(conversation_id)


class InterruptEventHandler(BaseEventHandler):
    """Event handler for processing interrupt events."""

    name: str = "interrupt_event_handler"
    description: str = "Handles conversation interrupt events"
    enabled: bool = True
    priority: int = 100  # High priority for interrupts
    supported_events: list = ["conversation.interrupt"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_service = AgentService()

    async def handle(self, event) -> bool:
        """Handle interrupt events.

        Args:
            event: The interrupt event to handle

        Returns:
            bool: True if handling was successful
        """
        try:
            if event.event_type != "conversation.interrupt":
                return True

            conversation_id = getattr(event, 'conversation_id', None)
            user_id = getattr(event, 'user_id', None)

            if not conversation_id or not user_id:
                logger.warning(f"Interrupt event missing conversation_id or user_id: {event.event_id}")
                return True

            # Handle agent interrupt
            success = await self.agent_service.interrupt_agent(
                conversation_id=conversation_id,
                user_id=user_id
            )

            if success:
                logger.info(f"Agent interrupt handled for conversation {conversation_id}")
            else:
                logger.warning(f"Agent interrupt failed for conversation {conversation_id}")

            return success

        except Exception as e:
            logger.error(f"Error in interrupt event handler for event {event.event_id}: {e}")
            return False
