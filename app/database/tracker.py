"""Event tracking implementation for managing event relationships and chains."""

from typing import List, Optional, Dict, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text
from collections import defaultdict, deque

from app.logger import logger
from app.database.persistence import EventPersistence


class EventTracker:
    """Event tracker for managing event relationships and chains."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.persistence = EventPersistence(session)
        self._session = session

    async def track_event_relations(self, event) -> bool:
        """Track event relationships and update root event ID.

        Args:
            event: The event to track

        Returns:
            bool: True if tracking was successful
        """
        try:
            # If event has parent events, find the root event
            if hasattr(event, 'parent_events') and event.parent_events:
                root_event_id = await self._find_root_event(event.parent_events[0])
                if root_event_id:
                    event.root_event_id = root_event_id
                else:
                    # If no root found, the first parent becomes the root
                    event.root_event_id = event.parent_events[0]
            else:
                # This is a root event
                event.root_event_id = event.event_id

            logger.debug(f"Event {event.event_id} tracked with root {event.root_event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to track event relations for {event.event_id}: {e}")
            return False

    async def get_event_chain(self, event_id: str):
        """Get the complete event chain starting from a root event.

        Args:
            event_id: The event ID to start from

        Returns:
            List[BaseEvent]: The complete event chain
        """
        try:
            # First get the event to find its root
            event = await self.persistence.get_event(event_id)
            if not event:
                return []

            root_event_id = getattr(event, 'root_event_id', event_id)

            # Get all events with the same root
            session = await self.persistence._get_session()
            close_session = self.persistence._session is None

            try:
                from app.database.models import Event as EventModel
                stmt = (
                    select(EventModel)
                    .where(
                        or_(
                            EventModel.root_event_id == root_event_id,
                            EventModel.id == root_event_id
                        )
                    )
                    .order_by(EventModel.timestamp)
                )

                result = await session.execute(stmt)
                event_models = result.scalars().all()

                events = [self.persistence._model_to_event(model) for model in event_models]

                # Build the chain using parent-child relationships
                return self._build_event_chain(events)

            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.error(f"Failed to get event chain for {event_id}: {e}")
            return []

    async def get_related_events(self, event_id: str,
                               relationship_types: Optional[List[str]] = None):
        """Get events related to the given event.

        Args:
            event_id: The event ID to find related events for
            relationship_types: Optional list of relationship types to filter by

        Returns:
            List[BaseEvent]: List of related events
        """
        try:
            event = await self.persistence.get_event(event_id)
            if not event:
                return []

            related_events = []

            # Get parent events
            if hasattr(event, 'parent_events') and event.parent_events:
                for parent_id in event.parent_events:
                    parent_event = await self.persistence.get_event(parent_id)
                    if parent_event:
                        related_events.append(parent_event)

            # Get child events (events that have this event as parent)
            child_events = await self._get_child_events(event_id)
            related_events.extend(child_events)

            # Get sibling events (events with same parent)
            if hasattr(event, 'parent_events') and event.parent_events:
                sibling_events = await self._get_sibling_events(event_id, event.parent_events[0])
                related_events.extend(sibling_events)

            # Remove duplicates
            seen_ids = set()
            unique_events = []
            for evt in related_events:
                if evt.event_id not in seen_ids:
                    seen_ids.add(evt.event_id)
                    unique_events.append(evt)

            return unique_events

        except Exception as e:
            logger.error(f"Failed to get related events for {event_id}: {e}")
            return []

    async def get_conversation_event_tree(self, conversation_id: str) -> Dict[str, Any]:
        """Get the event tree structure for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            Dict[str, Any]: Tree structure of events
        """
        try:
            events = await self.persistence.get_conversation_events(conversation_id)
            return self._build_event_tree(events)

        except Exception as e:
            logger.error(f"Failed to get event tree for conversation {conversation_id}: {e}")
            return {}

    async def _find_root_event(self, event_id: str) -> Optional[str]:
        """Find the root event ID for a given event.

        Args:
            event_id: The event ID to find root for

        Returns:
            Optional[str]: The root event ID if found
        """
        visited = set()
        current_id = event_id

        while current_id and current_id not in visited:
            visited.add(current_id)

            event = await self.persistence.get_event(current_id)
            if not event:
                break

            # If event has root_event_id, use it
            if hasattr(event, 'root_event_id') and event.root_event_id:
                return event.root_event_id

            # If event has parent, continue traversing
            if hasattr(event, 'parent_events') and event.parent_events:
                current_id = event.parent_events[0]
            else:
                # This is the root
                return current_id

        return current_id

    async def _get_child_events(self, parent_event_id: str):
        """Get all child events for a parent event.

        Args:
            parent_event_id: The parent event ID

        Returns:
            List[BaseEvent]: List of child events
        """
        session = await self.persistence._get_session()
        close_session = self.persistence._session is None

        try:
            from app.database.models import Event as EventModel
            # Use JSON contains query to find events with this parent
            stmt = select(EventModel).where(
                text("JSON_CONTAINS(parent_events, :parent_id)")
            ).params(parent_id=f'"{parent_event_id}"')

            result = await session.execute(stmt)
            event_models = result.scalars().all()

            return [self.persistence._model_to_event(model) for model in event_models]

        except Exception as e:
            logger.error(f"Failed to get child events for {parent_event_id}: {e}")
            return []
        finally:
            if close_session:
                await session.close()

    async def _get_sibling_events(self, event_id: str, parent_event_id: str):
        """Get sibling events (events with same parent).

        Args:
            event_id: The current event ID
            parent_event_id: The parent event ID

        Returns:
            List[BaseEvent]: List of sibling events
        """
        child_events = await self._get_child_events(parent_event_id)
        return [event for event in child_events if event.event_id != event_id]

    def _build_event_chain(self, events):
        """Build a chronological event chain from a list of events.

        Args:
            events: List of events to build chain from

        Returns:
            List[BaseEvent]: Chronologically ordered event chain
        """
        # Sort by timestamp
        return sorted(events, key=lambda e: e.timestamp)

    def _build_event_tree(self, events) -> Dict[str, Any]:
        """Build a tree structure from a list of events.

        Args:
            events: List of events to build tree from

        Returns:
            Dict[str, Any]: Tree structure
        """
        # Create event lookup
        event_map = {event.event_id: event for event in events}

        # Build parent-child relationships
        children_map = defaultdict(list)
        root_events = []

        for event in events:
            if hasattr(event, 'parent_events') and event.parent_events:
                # Add to parent's children
                for parent_id in event.parent_events:
                    if parent_id in event_map:
                        children_map[parent_id].append(event)
            else:
                # This is a root event
                root_events.append(event)

        def build_node(event) -> Dict[str, Any]:
            """Build a tree node for an event."""
            node = {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'timestamp': event.timestamp.isoformat(),
                'data': event.data,
                'children': []
            }

            # Add children
            for child in children_map.get(event.event_id, []):
                node['children'].append(build_node(child))

            return node

        # Build tree starting from root events
        tree = {
            'roots': [build_node(event) for event in root_events],
            'total_events': len(events)
        }

        return tree
