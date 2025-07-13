"""Global EventBus Manager for OpenManus project.

This module provides a singleton EventBusManager that manages the global event bus
instance and provides unified event publishing interfaces for system integration.
"""

import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime

from app.logger import logger
from app.event.bus import EventBus
from app.event.base import BaseEvent, BaseEventHandler
from app.event.events import *
from app.database.persistence import EventPersistence
from app.database.tracker import EventTracker


class EventBusManager:
    """Singleton manager for the global event bus.

    Provides unified access to event publishing and subscription across the system.
    Designed to integrate with existing architecture without breaking current patterns.
    """

    _instance: Optional['EventBusManager'] = None
    _bus: Optional[EventBus] = None
    _initialized: bool = False
    _persistence: Optional[EventPersistence] = None
    _tracker: Optional[EventTracker] = None

    def __new__(cls) -> 'EventBusManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self, bus_name: str = "OpenManus-EventBus",
                        enable_persistence: bool = True) -> None:
        """Initialize the global event bus."""
        if self._initialized:
            return

        self._bus = EventBus(name=bus_name)

        # Initialize persistence and tracking if enabled
        if enable_persistence:
            try:
                self._persistence = EventPersistence()
                self._tracker = EventTracker()
                logger.info("Event persistence and tracking enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize event persistence: {e}")
                logger.info("Continuing without persistence")

        self._initialized = True
        logger.info(f"EventBusManager initialized with bus: {bus_name}")

    @property
    def bus(self) -> EventBus:
        """Get the global event bus instance."""
        if not self._initialized or self._bus is None:
            raise RuntimeError("EventBusManager not initialized. Call initialize() first.")
        return self._bus

    async def publish(self, event: BaseEvent) -> bool:
        """Publish an event to the global bus."""
        if not self._initialized:
            logger.warning("EventBusManager not initialized, skipping event publication")
            return False

        # Track event relationships if tracker is available
        if self._tracker:
            await self._tracker.track_event_relations(event)

        # Publish to event bus
        result = await self._bus.publish(event)

        # Persist event if persistence is available
        if self._persistence and result:
            await self._persistence.store_event(event)

        return result

    async def subscribe(self, handler: BaseEventHandler) -> bool:
        """Subscribe a handler to the global bus."""
        if not self._initialized:
            logger.warning("EventBusManager not initialized, skipping handler subscription")
            return False
        return await self._bus.subscribe(handler)

    async def unsubscribe(self, handler_name: str) -> bool:
        """Unsubscribe a handler from the global bus."""
        if not self._initialized:
            return False
        return await self._bus.unsubscribe(handler_name)

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        if not self._initialized:
            return {"error": "EventBusManager not initialized"}
        return self._bus.get_event_stats()

    async def shutdown(self) -> None:
        """Shutdown the event bus."""
        if self._initialized and self._bus:
            await self._bus.shutdown()
            self._initialized = False
            logger.info("EventBusManager shutdown complete")

    # Persistence access methods
    async def get_event(self, event_id: str) -> Optional[BaseEvent]:
        """Get an event by ID."""
        if self._persistence:
            return await self._persistence.get_event(event_id)
        return None

    async def get_conversation_events(self, conversation_id: str) -> List[BaseEvent]:
        """Get all events for a conversation."""
        if self._persistence:
            return await self._persistence.get_conversation_events(conversation_id)
        return []

    async def get_event_chain(self, event_id: str) -> List[BaseEvent]:
        """Get the complete event chain for an event."""
        if self._tracker:
            return await self._tracker.get_event_chain(event_id)
        return []

    async def get_related_events(self, event_id: str) -> List[BaseEvent]:
        """Get events related to the given event."""
        if self._tracker:
            return await self._tracker.get_related_events(event_id)
        return []

    async def get_recent_events(self, limit: int = 10, conversation_id: Optional[str] = None,
                               event_type: Optional[str] = None) -> List[BaseEvent]:
        """Get recent events, optionally filtered by conversation or event type.

        Args:
            limit: Maximum number of events to return
            conversation_id: Optional conversation ID filter
            event_type: Optional event type filter

        Returns:
            List of recent events
        """
        if self._persistence:
            return await self._persistence.get_recent_events(
                limit=limit,
                conversation_id=conversation_id,
                event_type=event_type
            )
        return []


# Global instance
event_manager = EventBusManager()


# ============================================================================
# Integration Mixins and Decorators
# ============================================================================

class EventAwareMixin:
    """Mixin class to add event publishing capabilities to existing classes.

    Can be mixed into existing classes without breaking their functionality.
    """

    async def publish_event(self, event: BaseEvent) -> bool:
        """Publish an event through the global event bus."""
        # Set source if not already set
        if not event.source:
            event.source = getattr(self, 'name', self.__class__.__name__)

        # Set conversation_id if available and not set
        if hasattr(self, 'conversation_id') and not hasattr(event, 'conversation_id'):
            event.conversation_id = self.conversation_id

        return await event_manager.publish(event)

    async def publish_agent_step_start(self, step_number: int) -> bool:
        """Convenience method to publish agent step start events."""
        if hasattr(self, 'name'):
            total_steps = getattr(self, 'max_steps', 20)

            event = create_agent_step_start_event(
                agent_name=self.name,
                agent_type=self.__class__.__name__,
                step_number=step_number,
                conversation_id=getattr(self, 'conversation_id', None)
            )

            # Add total steps to event data
            event.data.update({
                'total_steps': total_steps
            })

            return await self.publish_event(event)
        return False

    async def publish_agent_step_complete(self, step_number: int, result: Optional[str] = None) -> bool:
        """Convenience method to publish agent step complete events."""
        if hasattr(self, 'name'):
            # Get additional step details if available
            thoughts = getattr(self, '_current_step_thoughts', '')
            tools_selected = getattr(self, '_current_step_tools', [])
            tool_count = getattr(self, '_current_step_tool_count', 0)
            total_steps = getattr(self, 'max_steps', 20)

            event = AgentStepCompleteEvent(
                agent_name=self.name,
                agent_type=self.__class__.__name__,
                step_number=step_number,
                result=result,
                conversation_id=getattr(self, 'conversation_id', None),
                source=self.name
            )

            # Add detailed information to event data
            event.data.update({
                'thoughts': thoughts,
                'tools_selected': tools_selected,
                'tool_count': tool_count,
                'total_steps': total_steps
            })

            return await self.publish_event(event)
        return False

    async def publish_tool_execution(self, tool_name: str, status: str,
                                   parameters: Dict[str, Any], result: Any = None) -> bool:
        """Convenience method to publish tool execution events."""
        event = create_tool_execution_event(
            tool_name=tool_name,
            tool_type="unknown",
            status=status,
            parameters=parameters,
            conversation_id=getattr(self, 'conversation_id', None)
        )
        return await self.publish_event(event)

    async def publish_error(self, error_type: str, error_message: str,
                          context: Dict[str, Any] = None) -> bool:
        """Convenience method to publish error events."""
        event = create_system_error_event(
            component=self.__class__.__name__,
            error_type=error_type,
            error_message=error_message,
            conversation_id=getattr(self, 'conversation_id', None)
        )
        if context:
            event.data.update({"context": context})
        return await self.publish_event(event)


def event_publisher(event_type: str = None):
    """Decorator to automatically publish events for method calls.

    Usage:
        @event_publisher("agent.step.completed")
        async def step(self):
            # Original method logic
            pass
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # Determine event type
            method_event_type = event_type or f"{self.__class__.__name__.lower()}.{func.__name__}"

            # Create start event
            start_event = BaseEvent(
                event_type=f"{method_event_type}.start",
                source=getattr(self, 'name', self.__class__.__name__),
                data={
                    "method": func.__name__,
                    "args": str(args)[:200],  # Limit size
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()},
                }
            )

            # Set conversation_id if available
            if hasattr(self, 'conversation_id'):
                start_event.conversation_id = self.conversation_id

            try:
                await event_manager.publish(start_event)

                # Execute original method
                result = await func(self, *args, **kwargs)

                # Create completion event
                complete_event = BaseEvent(
                    event_type=f"{method_event_type}.completed",
                    source=getattr(self, 'name', self.__class__.__name__),
                    data={
                        "method": func.__name__,
                        "result": str(result)[:200] if result else None,
                    }
                )

                if hasattr(self, 'conversation_id'):
                    complete_event.conversation_id = self.conversation_id

                await event_manager.publish(complete_event)

                return result

            except Exception as e:
                # Create error event
                error_event = create_system_error_event(
                    component=self.__class__.__name__,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    conversation_id=getattr(self, 'conversation_id', None)
                )
                error_event.data.update({
                    "method": func.__name__,
                    "args": str(args)[:200],
                })
                await event_manager.publish(error_event)
                raise

        return wrapper
    return decorator


@asynccontextmanager
async def event_context(event_type: str, source: str = None, conversation_id: str = None, **event_data):
    """Context manager for event-aware operations.

    Usage:
        async with event_context("tool.execution", tool_name="python"):
            # Your code here
            result = await some_operation()
    """
    start_event = BaseEvent(
        event_type=f"{event_type}.start",
        source=source,
        data=event_data
    )

    if conversation_id:
        start_event.conversation_id = conversation_id

    try:
        await event_manager.publish(start_event)
        yield

        complete_event = BaseEvent(
            event_type=f"{event_type}.completed",
            source=source,
            data=event_data
        )

        if conversation_id:
            complete_event.conversation_id = conversation_id

        await event_manager.publish(complete_event)

    except Exception as e:
        error_event = create_system_error_event(
            component=source or "unknown",
            error_type=type(e).__name__,
            error_message=str(e),
            conversation_id=conversation_id
        )
        error_event.data.update(event_data)
        await event_manager.publish(error_event)
        raise


# ============================================================================
# Utility Functions
# ============================================================================

async def ensure_event_manager_initialized():
    """Ensure the global event manager is initialized."""
    if not event_manager._initialized:
        await event_manager.initialize()


async def publish_system_startup():
    """Publish system startup event."""
    await ensure_event_manager_initialized()
    event = SystemEvent(
        component="system",
        event_type="system.startup",
        data={"timestamp": datetime.now().isoformat()}
    )
    await event_manager.publish(event)


async def publish_system_shutdown():
    """Publish system shutdown event."""
    if event_manager._initialized:
        event = SystemEvent(
            component="system",
            event_type="system.shutdown",
            data={"timestamp": datetime.now().isoformat()}
        )
        await event_manager.publish(event)
        await event_manager.shutdown()
