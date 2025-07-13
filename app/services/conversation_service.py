"""Conversation service for managing user conversations and messages."""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload

from app.logger import logger
from app.database.models import User, Conversation, Event
from app.database.database import AsyncSessionLocal
from app.event.manager import event_manager
from app.event.events import (
    create_conversation_created_event,
    create_user_input_event,
    create_interrupt_event,
    ConversationClosedEvent
)


class ConversationService:
    """Service for conversation management and message processing."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def _get_session(self) -> tuple[AsyncSession, bool]:
        """Get database session and whether it should be closed.

        Returns:
            tuple[AsyncSession, bool]: (session, should_close)
        """
        if self._session:
            return self._session, False
        return AsyncSessionLocal(), True

    async def create_conversation(self, user_id: str, title: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> Optional[Conversation]:
        """Create a new conversation for a user.

        Args:
            user_id: User ID
            title: Optional conversation title
            metadata: Optional conversation metadata

        Returns:
            Optional[Conversation]: Created conversation if successful, None otherwise
        """
        try:
            session, close_session = await self._get_session()

            try:
                # Verify user exists
                user_stmt = select(User).where(User.id == user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()

                if not user:
                    logger.warning(f"Cannot create conversation: user not found - {user_id}")
                    return None

                # Create conversation
                conversation = Conversation(
                    user_id=user_id,
                    title=title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    status="active",
                    metadata_=metadata or {}
                )

                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)

                # Publish conversation created event
                event = create_conversation_created_event(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    title=conversation.title
                )
                await event_manager.publish(event)

                logger.info(f"Created conversation {conversation.id} for user {user_id}")
                return conversation

            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to create conversation for user {user_id}: {e}")
            return None

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID.

        Args:
            conversation_id: Conversation ID

        Returns:
            Optional[Conversation]: Conversation if found, None otherwise
        """
        try:
            session, close_session = await self._get_session()

            try:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalar_one_or_none()

                return conversation
            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    async def get_user_conversations(self, user_id: str,
                                   limit: int = 50, offset: int = 0) -> List[Conversation]:
        """Get conversations for a user.

        Args:
            user_id: User ID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List[Conversation]: List of user's conversations
        """
        try:
            session, close_session = await self._get_session()

            try:
                stmt = (
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                conversations = result.scalars().all()

                return list(conversations)
            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to get conversations for user {user_id}: {e}")
            return []

    async def update_conversation(self, conversation_id: str,
                                title: Optional[str] = None,
                                status: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update conversation details.

        Args:
            conversation_id: Conversation ID
            title: New title (optional)
            status: New status (optional)
            metadata: New metadata (optional)

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            session, close_session = await self._get_session()

            try:
                # Build update values
                update_values = {"updated_at": datetime.now()}
                if title is not None:
                    update_values["title"] = title
                if status is not None:
                    update_values["status"] = status
                if metadata is not None:
                    update_values["metadata_"] = metadata

                stmt = (
                    update(Conversation)
                    .where(Conversation.id == conversation_id)
                    .values(**update_values)
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Updated conversation {conversation_id}")
                    return True
                else:
                    logger.warning(f"No conversation found to update: {conversation_id}")
                    return False

            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to update conversation {conversation_id}: {e}")
            return False

    async def close_conversation(self, conversation_id: str,
                               reason: str = "user_closed") -> bool:
        """Close a conversation.

        Args:
            conversation_id: Conversation ID
            reason: Reason for closing

        Returns:
            bool: True if closed successfully, False otherwise
        """
        try:
            # Get conversation to get user_id
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                return False

            # Update status to closed
            success = await self.update_conversation(
                conversation_id=conversation_id,
                status="closed"
            )

            if success:
                # Publish conversation closed event
                event = ConversationClosedEvent(
                    conversation_id=conversation_id,
                    user_id=conversation.user_id,
                    reason=reason
                )
                await event_manager.publish(event)

                logger.info(f"Closed conversation {conversation_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to close conversation {conversation_id}: {e}")
            return False

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all associated data.

        Args:
            conversation_id: Conversation ID

        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            session, close_session = await self._get_session()

            try:
                # Delete conversation (cascading will handle events)
                stmt = delete(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted conversation {conversation_id}")
                    return True
                else:
                    logger.warning(f"No conversation found to delete: {conversation_id}")
                    return False

            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False

    async def send_message(self, conversation_id: str, user_id: str,
                          message: str, parent_event_id: Optional[str] = None) -> Optional[str]:
        """Send a message in a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            message: Message content
            parent_event_id: Optional parent event ID for threading

        Returns:
            Optional[str]: Event ID of the created user input event, None if failed
        """
        try:
            # Verify conversation exists and user has access
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"Cannot send message: conversation not found - {conversation_id}")
                return None

            if conversation.user_id != user_id:
                logger.warning(f"Cannot send message: user {user_id} not authorized for conversation {conversation_id}")
                return None

            if conversation.status != "active":
                logger.warning(f"Cannot send message: conversation {conversation_id} is not active")
                return None

            # Create user input event
            event = create_user_input_event(
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
                parent_event_id=parent_event_id
            )

            # Publish event
            success = await event_manager.publish(event)
            if success:
                # Update conversation timestamp
                await self.update_conversation(conversation_id)
                logger.info(f"Message sent in conversation {conversation_id}")
                return event.event_id
            else:
                logger.error(f"Failed to publish user input event for conversation {conversation_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to send message in conversation {conversation_id}: {e}")
            return None

    async def interrupt_conversation(self, conversation_id: str, user_id: str,
                                   interrupted_event_id: Optional[str] = None) -> bool:
        """Interrupt an ongoing conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            interrupted_event_id: Optional ID of the event being interrupted

        Returns:
            bool: True if interrupt successful, False otherwise
        """
        try:
            # Verify conversation exists and user has access
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"Cannot interrupt: conversation not found - {conversation_id}")
                return False

            if conversation.user_id != user_id:
                logger.warning(f"Cannot interrupt: user {user_id} not authorized for conversation {conversation_id}")
                return False

            # Create interrupt event
            event = create_interrupt_event(
                conversation_id=conversation_id,
                user_id=user_id,
                interrupted_event_id=interrupted_event_id
            )

            # Publish event
            success = await event_manager.publish(event)
            if success:
                logger.info(f"Conversation {conversation_id} interrupted by user {user_id}")
                return True
            else:
                logger.error(f"Failed to publish interrupt event for conversation {conversation_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to interrupt conversation {conversation_id}: {e}")
            return False

    async def get_conversation_history(self, conversation_id: str, user_id: str,
                                     limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get conversation history as formatted messages.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List[Dict[str, Any]]: List of formatted message events
        """
        try:
            # Verify user has access to conversation
            conversation = await self.get_conversation(conversation_id)
            if not conversation or conversation.user_id != user_id:
                logger.warning(f"User {user_id} not authorized to view conversation {conversation_id}")
                return []

            # Get conversation events
            events = await event_manager.get_conversation_events(conversation_id)

            # Filter and format message events
            message_events = []
            for event in events:
                if event.event_type in ['conversation.userinput', 'conversation.agentresponse', 'conversation.interrupted']:
                    formatted_event = {
                        'event_id': event.event_id,
                        'event_type': event.event_type,
                        'timestamp': event.timestamp.isoformat(),
                        'data': event.data,
                        'status': event.status.value
                    }

                    # Add role and content for message rendering
                    if event.event_type == 'conversation.userinput':
                        formatted_event['role'] = 'user'
                        formatted_event['content'] = event.data.get('message', '')
                    elif event.event_type == 'conversation.agentresponse':
                        formatted_event['role'] = 'assistant'
                        formatted_event['content'] = event.data.get('response', '')
                    elif event.event_type == 'conversation.interrupted':
                        formatted_event['role'] = 'system'
                        formatted_event['content'] = f"Conversation interrupted: {event.data.get('reason', 'unknown')}"

                    message_events.append(formatted_event)

            # Apply pagination
            start_idx = offset
            end_idx = offset + limit
            return message_events[start_idx:end_idx]

        except Exception as e:
            logger.error(f"Failed to get conversation history {conversation_id}: {e}")
            return []
