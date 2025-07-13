"""Concrete implementation of the event bus system."""

import asyncio
from typing import Any, Dict, List, Optional

from app.logger import logger
from app.event.base import BaseEvent, BaseEventBus, BaseEventHandler
from app.event.types import EventStatus


class EventBus(BaseEventBus):
    """Concrete implementation of the event bus.

    This implementation provides asynchronous event processing with
    concurrent handler execution and proper error handling.
    """

    def __init__(self, **kwargs):
        """Initialize the event bus."""
        super().__init__(**kwargs)
        self._processing_semaphore = asyncio.Semaphore(self.max_concurrent_events)
        self._shutdown = False

    async def publish(self, event: BaseEvent) -> bool:
        """Publish an event to the bus for processing.

        Args:
            event: The event to publish

        Returns:
            bool: True if event was published successfully
        """
        if self._shutdown:
            logger.warning(f"Event bus is shutting down, rejecting event {event.event_id}")
            return False

        try:
            logger.info(f"Publishing event {event.event_id} ({event.event_type}) from {event.source}")

            # Add to active events
            self.active_events[event.event_id] = event

            # Process event asynchronously
            asyncio.create_task(self._process_event(event))

            return True

        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {str(e)}")
            event.mark_failed(f"Publication failed: {str(e)}")
            return False

    async def subscribe(self, handler: BaseEventHandler) -> bool:
        """Subscribe a handler to the event bus.

        Args:
            handler: The event handler to register

        Returns:
            bool: True if handler was registered successfully
        """
        try:
            if handler.name in self.handlers:
                logger.warning(f"Handler '{handler.name}' is already registered, replacing")

            self.handlers[handler.name] = handler
            logger.info(f"Registered event handler: {handler.name}")

            return True

        except Exception as e:
            logger.error(f"Failed to register handler '{handler.name}': {str(e)}")
            return False

    async def unsubscribe(self, handler_name: str) -> bool:
        """Unsubscribe a handler from the event bus.

        Args:
            handler_name: Name of the handler to unregister

        Returns:
            bool: True if handler was unregistered successfully
        """
        try:
            if handler_name not in self.handlers:
                logger.warning(f"Handler '{handler_name}' not found for unsubscription")
                return False

            del self.handlers[handler_name]
            logger.info(f"Unregistered event handler: {handler_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to unregister handler '{handler_name}': {str(e)}")
            return False

    async def _process_event(self, event: BaseEvent) -> None:
        """Process an event through all compatible handlers.

        Args:
            event: The event to process
        """
        async with self._processing_semaphore:
            try:
                # Get compatible handlers
                handlers = self.get_handlers_for_event(event)

                if not handlers:
                    logger.warning(f"No handlers found for event {event.event_id} ({event.event_type})")
                    event.mark_completed()  # Mark as completed even if no handlers
                    return

                logger.debug(f"Processing event {event.event_id} with {len(handlers)} handlers")

                # Process with all compatible handlers concurrently
                tasks = [handler.safe_handle(event) for handler in handlers]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results
                success_count = sum(1 for result in results if result is True)
                error_count = sum(1 for result in results if isinstance(result, Exception))

                if error_count > 0:
                    logger.warning(f"Event {event.event_id} had {error_count} handler errors")

                if success_count > 0:
                    event.mark_completed()
                    logger.debug(f"Event {event.event_id} processed successfully by {success_count} handlers")
                else:
                    event.mark_failed("No handlers processed the event successfully")
                    logger.error(f"Event {event.event_id} failed - no successful handlers")

            except Exception as e:
                error_msg = f"Unexpected error processing event {event.event_id}: {str(e)}"
                logger.error(error_msg)
                event.mark_failed(error_msg)

            finally:
                # Move from active to history
                if event.event_id in self.active_events:
                    del self.active_events[event.event_id]
                self.add_to_history(event)

    async def shutdown(self) -> None:
        """Gracefully shutdown the event bus.

        Waits for all active events to complete processing.
        """
        logger.info("Shutting down event bus...")
        self._shutdown = True

        # Wait for active events to complete
        while self.active_events:
            logger.info(f"Waiting for {len(self.active_events)} active events to complete...")
            await asyncio.sleep(0.1)

        logger.info("Event bus shutdown complete")

    async def wait_for_event(self, event_id: str, timeout: Optional[float] = None) -> Optional[BaseEvent]:
        """Wait for a specific event to complete processing.

        Args:
            event_id: ID of the event to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Optional[BaseEvent]: The completed event if found, None if timeout
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if event is in history (completed)
            for event in reversed(self.event_history):
                if event.event_id == event_id:
                    return event

            # Check timeout
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                return None

            # Check if event is still active
            if event_id not in self.active_events:
                return None

            await asyncio.sleep(0.1)
