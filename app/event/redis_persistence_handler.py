"""Redis-based event persistence handler."""

from typing import Set

from app.event.base import BaseEvent, BaseEventHandler
from app.database.redis_persistence import redis_persistence
from app.logger import logger


class RedisPersistenceHandler(BaseEventHandler):
    """Redis-based event persistence handler."""

    def __init__(self):
        # Initialize with required Pydantic fields
        super().__init__(
            name="redis_persistence_handler",
            description="Stores events in Redis for high-performance access",
            priority=100,
            supported_events=[
                'conversation.conversationcreated',
                'conversation.conversationupdated',
                'conversation.conversationdeleted',
                'conversation.userinput',
                'conversation.agentresponse',
                'conversation.messageprocessed',
                'conversation.interrupted',
                'user.userauthenticated',
                'user.userloggedout',
                'system.systemerror',
                'system.systemwarning',
                'agent.agentstarted',
                'agent.agentcompleted',
                'agent.agenterror',
            ]
        )
        self.persistence = redis_persistence

        # Define which event types should be persisted (for backward compatibility)
        self.persistent_event_types: Set[str] = set(self.supported_events)

    async def handle(self, event: BaseEvent) -> bool:
        """Handle event persistence to Redis.

        Args:
            event: Event to handle

        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            # Check if this event type should be persisted
            if event.event_type not in self.persistent_event_types:
                logger.debug(f"Event type {event.event_type} not configured for persistence, skipping")
                return True

            # Store event in Redis
            success = await self.persistence.store_event(event)

            if success:
                logger.debug(f"Event {event.event_id} persisted to Redis successfully")
                return True
            else:
                logger.warning(f"Failed to persist event {event.event_id} to Redis")
                return False

        except Exception as e:
            logger.error(f"Redis persistence handler error for event {event.event_id}: {e}")
            return False

    def can_handle(self, event: BaseEvent) -> bool:
        """Check if this handler can handle the event.

        Args:
            event: Event to check

        Returns:
            bool: True if can handle, False otherwise
        """
        return event.event_type in self.persistent_event_types

# Note: handler_name and priority are now Pydantic fields in the base class
