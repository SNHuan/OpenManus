"""Event handler for automatic event persistence."""

from typing import Optional
from app.logger import logger
from app.event.base import BaseEventHandler
from app.database.persistence import EventPersistence
from app.database.tracker import EventTracker


class PersistenceEventHandler(BaseEventHandler):
    """Event handler that automatically persists events to database."""

    name: str = "persistence_handler"
    description: str = "Automatically persists all events to database"
    enabled: bool = True
    priority: int = 1000  # High priority to ensure persistence happens first

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.persistence = EventPersistence()
        self.tracker = EventTracker()

    async def handle(self, event) -> bool:
        """Handle event by persisting it to database.

        Args:
            event: The event to persist

        Returns:
            bool: True if persistence was successful
        """
        try:
            # Track event relationships
            await self.tracker.track_event_relations(event)

            # Persist the event
            success = await self.persistence.store_event(event)

            if success:
                logger.debug(f"Event {event.event_id} persisted successfully")
            else:
                logger.warning(f"Failed to persist event {event.event_id}")

            return success

        except Exception as e:
            logger.error(f"Error in persistence handler for event {event.event_id}: {e}")
            return False


class ConversationEventHandler(BaseEventHandler):
    """Event handler for conversation-specific events."""

    name: str = "conversation_handler"
    description: str = "Handles conversation lifecycle events"
    enabled: bool = True
    priority: int = 500
    supported_events: list = [
        "conversation.created",
        "conversation.closed",
        "user.input",
        "interrupt"
    ]

    async def handle(self, event) -> bool:
        """Handle conversation events.

        Args:
            event: The conversation event to handle

        Returns:
            bool: True if handling was successful
        """
        try:
            if event.event_type == "conversation.created":
                return await self._handle_conversation_created(event)
            elif event.event_type == "conversation.closed":
                return await self._handle_conversation_closed(event)
            elif event.event_type == "user.input":
                return await self._handle_user_input(event)
            elif event.event_type == "interrupt":
                return await self._handle_interrupt(event)

            return True

        except Exception as e:
            logger.error(f"Error in conversation handler for event {event.event_id}: {e}")
            return False

    async def _handle_conversation_created(self, event) -> bool:
        """Handle conversation creation event."""
        logger.info(f"New conversation created: {event.data.get('conversation_id')}")
        return True

    async def _handle_conversation_closed(self, event) -> bool:
        """Handle conversation closure event."""
        logger.info(f"Conversation closed: {event.data.get('conversation_id')}")
        return True

    async def _handle_user_input(self, event) -> bool:
        """Handle user input event."""
        message_length = event.data.get('input_length', 0)
        logger.debug(f"User input received: {message_length} characters")
        return True

    async def _handle_interrupt(self, event) -> bool:
        """Handle interrupt event."""
        reason = event.data.get('reason', 'unknown')
        logger.info(f"Conversation interrupted: {reason}")
        return True


class SystemMonitoringHandler(BaseEventHandler):
    """Event handler for system monitoring and metrics."""

    name: str = "system_monitoring_handler"
    description: str = "Monitors system events and collects metrics"
    enabled: bool = True
    priority: int = 100

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_counts = {}
        self.error_counts = {}

    async def handle(self, event) -> bool:
        """Handle event for monitoring purposes.

        Args:
            event: The event to monitor

        Returns:
            bool: Always returns True as monitoring should not fail event processing
        """
        try:
            # Count events by type
            event_type = event.event_type
            self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1

            # Track errors
            if event.status.value == "failed" or event.error_message:
                self.error_counts[event_type] = self.error_counts.get(event_type, 0) + 1
                logger.warning(f"Error event detected: {event_type} - {event.error_message}")

            # Log high-priority events
            if event.priority.value == "high":
                logger.info(f"High priority event: {event_type}")

            return True

        except Exception as e:
            logger.error(f"Error in monitoring handler: {e}")
            return True  # Don't fail the event processing

    def get_metrics(self) -> dict:
        """Get collected metrics."""
        return {
            "event_counts": self.event_counts.copy(),
            "error_counts": self.error_counts.copy(),
            "total_events": sum(self.event_counts.values()),
            "total_errors": sum(self.error_counts.values()),
        }
