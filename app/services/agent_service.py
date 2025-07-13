"""Agent service for integrating existing agent system with conversations."""

import asyncio
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.agent.manus import Manus
from app.services.conversation_service import ConversationService
from app.event.manager import event_manager
from app.event.events import AgentResponseEvent
from app.database.database import AsyncSessionLocal


class AgentService:
    """Service for managing agent execution in conversations."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session
        self.conversation_service = ConversationService(session)

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        return AsyncSessionLocal()

    async def process_user_message(self, conversation_id: str, user_id: str,
                                 message: str, event_id: str) -> bool:
        """Process a user message with an agent.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            message: User message
            event_id: Event ID of the user input event

        Returns:
            bool: True if processing was successful
        """
        try:
            # Verify conversation exists and user has access
            conversation = await self.conversation_service.get_conversation(conversation_id)
            if not conversation or conversation.user_id != user_id:
                logger.warning(f"User {user_id} not authorized for conversation {conversation_id}")
                return False

            # Create and configure agent
            agent = await self._create_agent(conversation_id)
            if not agent:
                logger.error(f"Failed to create agent for conversation {conversation_id}")
                return False

            # Run agent with the user message
            logger.info(f"Starting agent processing for conversation {conversation_id}")
            result = await agent.run(message, conversation_id=conversation_id)

            # Extract the final response from the result
            # The result is a summary of all steps, we want the actual response
            final_response = await self._extract_final_response(agent, result)

            # Publish agent response event
            response_event = AgentResponseEvent(
                agent_name=agent.name,
                agent_type=agent.__class__.__name__,
                response=final_response,
                conversation_id=conversation_id,
                user_id=user_id
            )
            response_event.parent_events = [event_id]  # Link to user input event

            await event_manager.publish(response_event)

            logger.info(f"Agent processing completed for conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Agent processing error for conversation {conversation_id}: {e}")

            # Publish error event
            from app.event.events import create_system_error_event
            error_event = create_system_error_event(
                component="agent_service",
                error_type=type(e).__name__,
                error_message=str(e),
                conversation_id=conversation_id
            )
            await event_manager.publish(error_event)

            return False

    async def _create_agent(self, conversation_id: str) -> Optional[Manus]:
        """Create and configure an agent for the conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Optional[Manus]: Configured agent instance
        """
        try:
            # Create Manus agent
            agent = await Manus.create()

            # Set conversation ID for event tracking
            agent.conversation_id = conversation_id

            # Load conversation history into agent memory
            await self._load_conversation_history(agent, conversation_id)

            return agent

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return None

    async def _load_conversation_history(self, agent: Manus, conversation_id: str):
        """Load conversation history into agent memory.

        Args:
            agent: Agent instance
            conversation_id: Conversation ID
        """
        try:
            # Get conversation events
            events = await event_manager.get_conversation_events(conversation_id)

            # Filter for message events and load into agent memory
            for event in events:
                # Handle user input events
                if event.event_type in ["user.input", "conversation.userinput"]:
                    message = event.data.get("message", "")
                    if message:
                        agent.update_memory("user", message)
                        logger.debug(f"Loaded user message: {message[:50]}...")

                # Handle agent response events
                elif event.event_type in ["agent.response", "conversation.agentresponse"]:
                    response = event.data.get("response", "")
                    if response:
                        agent.update_memory("assistant", response)
                        logger.debug(f"Loaded agent response: {response[:50]}...")

            logger.info(f"Loaded {len(events)} events into agent memory for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")

    async def _extract_final_response(self, agent: Manus, result: str) -> str:
        """Extract the final response from agent execution result.

        Args:
            agent: Agent instance
            result: Agent execution result

        Returns:
            str: Final response to send to user
        """
        try:
            # Get the last assistant message from agent memory
            messages = agent.memory.messages
            for message in reversed(messages):
                if message.role == "assistant" and message.content:
                    # Skip tool-related messages and get actual response
                    if not message.content.startswith("Observed output of cmd"):
                        return message.content

            # Fallback to the result summary if no assistant message found
            return result

        except Exception as e:
            logger.error(f"Failed to extract final response: {e}")
            return result

    async def interrupt_agent(self, conversation_id: str, user_id: str) -> bool:
        """Interrupt agent processing for a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            bool: True if interrupt was successful
        """
        try:
            # Mark any active agents for this conversation as interrupted
            interrupted_count = 0

            # Check if we have any active agents for this conversation
            # Note: In a more complex system, we might maintain a registry of active agents
            # For now, we'll rely on the event system and agent's self-checking mechanism

            logger.info(f"Agent interrupt requested for conversation {conversation_id}")

            # The interrupt will be handled by:
            # 1. The interrupt event being published (done by conversation service)
            # 2. Agents checking for interrupt events during their execution loop
            # 3. Agents checking their _interrupted flag

            return True

        except Exception as e:
            logger.error(f"Agent interrupt error: {e}")
            return False


class ConversationAgentHandler:
    """Event handler for processing user messages with agents."""

    def __init__(self):
        self.agent_service = AgentService()
        self._processing_conversations = set()

    async def handle_user_input(self, event):
        """Handle user input events by processing with agent.

        Args:
            event: User input event
        """
        try:
            conversation_id = getattr(event, 'conversation_id', None)
            user_id = getattr(event, 'user_id', None)

            if not conversation_id or not user_id:
                return

            # Avoid concurrent processing for the same conversation
            if conversation_id in self._processing_conversations:
                logger.info(f"Conversation {conversation_id} already being processed, skipping")
                return

            self._processing_conversations.add(conversation_id)

            try:
                message = event.data.get("message", "")
                if message.strip():
                    # Process message with agent in background
                    asyncio.create_task(
                        self.agent_service.process_user_message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            message=message,
                            event_id=event.event_id
                        )
                    )
            finally:
                # Remove from processing set after a delay to allow agent to start
                asyncio.create_task(self._remove_from_processing(conversation_id))

        except Exception as e:
            logger.error(f"Error handling user input event: {e}")

    async def _remove_from_processing(self, conversation_id: str):
        """Remove conversation from processing set after delay.

        Args:
            conversation_id: Conversation ID
        """
        await asyncio.sleep(1)  # Small delay to allow agent to start
        self._processing_conversations.discard(conversation_id)


# Global conversation agent handler
conversation_agent_handler = ConversationAgentHandler()
