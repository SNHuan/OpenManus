"""Event persistence implementation for storing events to database."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.logger import logger
from app.database.database import AsyncSessionLocal


class EventPersistence:
    """Event persistence handler for storing and retrieving events."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        return AsyncSessionLocal()

    async def store_event(self, event) -> bool:
        """Store an event to the database.

        Args:
            event: The event to store

        Returns:
            bool: True if stored successfully, False otherwise
        """
        session = await self._get_session()
        close_session = self._session is None

        try:
            # Import here to avoid circular import
            from app.database.models import Event as EventModel

            # Convert BaseEvent to EventModel
            event_model = EventModel(
                id=event.event_id,
                event_type=event.event_type,
                source=event.source,
                conversation_id=getattr(event, 'conversation_id', None),
                user_id=getattr(event, 'user_id', None),
                session_id=getattr(event, 'session_id', None),
                timestamp=event.timestamp,
                parent_events=getattr(event, 'parent_events', []),
                root_event_id=getattr(event, 'root_event_id', None),
                data=event.data,
                metadata_=event.metadata,
                status=event.status.value,
                processed_by=event.processed_by,
                error_message=event.error_message,
            )

            # Use merge to handle duplicate events gracefully
            try:
                session.add(event_model)
                await session.commit()
                logger.debug(f"Event {event.event_id} stored successfully")
                return True
            except Exception as commit_error:
                await session.rollback()

                # Check if it's a duplicate key error
                if "UNIQUE constraint failed" in str(commit_error):
                    logger.debug(f"Event {event.event_id} already exists, skipping")
                    return True  # Consider it successful since the event exists
                else:
                    logger.error(f"Failed to store event {event.event_id}: {commit_error}")
                    return False

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to store event {event.event_id}: {e}")
            return False
        finally:
            if close_session and session:
                try:
                    # Ensure session is properly closed
                    if hasattr(session, 'close'):
                        await session.close()
                except Exception as e:
                    logger.error(f"Error closing session: {e}")
                finally:
                    # Force cleanup
                    session = None

    async def get_event(self, event_id: str):
        """Get a single event by ID.

        Args:
            event_id: The event ID to retrieve

        Returns:
            Optional[BaseEvent]: The event if found, None otherwise
        """
        session = await self._get_session()
        close_session = self._session is None

        try:
            from app.database.models import Event as EventModel
            stmt = select(EventModel).where(EventModel.id == event_id)
            result = await session.execute(stmt)
            event_model = result.scalar_one_or_none()

            if event_model:
                return self._model_to_event(event_model)
            return None

        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None
        finally:
            if close_session:
                await session.close()

    async def get_conversation_events(self, conversation_id: str,
                                    limit: Optional[int] = None,
                                    offset: int = 0):
        """Get all events for a conversation.

        Args:
            conversation_id: The conversation ID
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List[BaseEvent]: List of events for the conversation
        """
        session = await self._get_session()
        close_session = self._session is None

        try:
            from app.database.models import Event as EventModel
            stmt = (
                select(EventModel)
                .where(EventModel.conversation_id == conversation_id)
                .order_by(EventModel.timestamp)
                .offset(offset)
            )

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            event_models = result.scalars().all()

            return [self._model_to_event(model) for model in event_models]

        except Exception as e:
            logger.error(f"Failed to get conversation events {conversation_id}: {e}")
            return []
        finally:
            if close_session:
                await session.close()

    async def get_events_by_type(self, event_type: str,
                               conversation_id: Optional[str] = None,
                               limit: Optional[int] = None):
        """Get events by type.

        Args:
            event_type: The event type to filter by
            conversation_id: Optional conversation ID to filter by
            limit: Maximum number of events to return

        Returns:
            List[BaseEvent]: List of matching events
        """
        session = await self._get_session()
        close_session = self._session is None

        try:
            from app.database.models import Event as EventModel
            conditions = [EventModel.event_type == event_type]
            if conversation_id:
                conditions.append(EventModel.conversation_id == conversation_id)

            stmt = (
                select(EventModel)
                .where(and_(*conditions))
                .order_by(desc(EventModel.timestamp))
            )

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            event_models = result.scalars().all()

            return [self._model_to_event(model) for model in event_models]

        except Exception as e:
            logger.error(f"Failed to get events by type {event_type}: {e}")
            return []
        finally:
            if close_session:
                await session.close()

    async def get_recent_events(self, limit: int = 100,
                              conversation_id: Optional[str] = None,
                              event_type: Optional[str] = None):
        """Get recent events.

        Args:
            limit: Maximum number of events to return
            conversation_id: Optional conversation ID to filter by
            event_type: Optional event type to filter by

        Returns:
            List[BaseEvent]: List of recent events
        """
        session = await self._get_session()
        close_session = self._session is None

        try:
            from app.database.models import Event as EventModel
            stmt = select(EventModel).order_by(desc(EventModel.timestamp)).limit(limit)

            conditions = []
            if conversation_id:
                conditions.append(EventModel.conversation_id == conversation_id)
            if event_type:
                conditions.append(EventModel.event_type == event_type)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            event_models = result.scalars().all()

            return [self._model_to_event(model) for model in event_models]

        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []
        finally:
            if close_session:
                await session.close()

    def _model_to_event(self, model):
        """Convert EventModel to BaseEvent.

        Args:
            model: The EventModel instance

        Returns:
            BaseEvent: The converted event
        """
        from app.event.types import EventStatus
        from app.event.base import BaseEvent

        event = BaseEvent(
            event_id=model.id,
            event_type=model.event_type,
            timestamp=model.timestamp,
            source=model.source,
            status=EventStatus(model.status),
            data=model.data or {},
            metadata=model.metadata_ or {},
            processed_by=model.processed_by or [],
            error_message=model.error_message,
        )

        # Set additional attributes
        if model.conversation_id:
            event.conversation_id = model.conversation_id
        if model.user_id:
            event.user_id = model.user_id
        if model.session_id:
            event.session_id = model.session_id
        if model.parent_events:
            event.parent_events = model.parent_events
        if model.root_event_id:
            event.root_event_id = model.root_event_id

        return event
