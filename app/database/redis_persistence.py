"""Redis-based event persistence."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.event.base import BaseEvent
from app.database.redis_client import redis_client
from app.logger import logger


class RedisEventPersistence:
    """Redis-based event persistence handler."""

    def __init__(self):
        self.redis = redis_client

    async def store_event(self, event: BaseEvent) -> bool:
        """Store event in Redis.

        Args:
            event: Event to store

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert event to dictionary
            event_data = {
                'id': event.event_id,
                'event_type': event.event_type,
                'source': event.source,
                'conversation_id': getattr(event, 'conversation_id', None),
                'user_id': getattr(event, 'user_id', None),
                'session_id': getattr(event, 'session_id', None),
                'timestamp': event.timestamp.timestamp() if isinstance(event.timestamp, datetime) else event.timestamp,
                'parent_events': json.dumps(getattr(event, 'parent_events', [])),
                'root_event_id': getattr(event, 'root_event_id', None),
                'data': json.dumps(event.data) if event.data else '{}',
                'metadata': json.dumps(event.metadata) if event.metadata else '{}',
                'status': event.status.value if hasattr(event.status, 'value') else str(event.status),
                'processed_by': json.dumps(event.processed_by) if event.processed_by else '[]',
                'error_message': event.error_message,
            }

            # Remove None values
            event_data = {k: v for k, v in event_data.items() if v is not None}

            # Store in Redis
            success = await self.redis.store_event(event_data)

            if success:
                logger.debug(f"Event {event.event_id} stored in Redis successfully")
            else:
                logger.error(f"Failed to store event {event.event_id} in Redis")

            return success

        except Exception as e:
            logger.error(f"Failed to store event {event.event_id} in Redis: {e}")
            return False

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID.

        Args:
            event_id: Event ID

        Returns:
            Optional[Dict[str, Any]]: Event data if found, None otherwise
        """
        try:
            event_data = await self.redis.get_event(event_id)

            if event_data:
                # Parse JSON fields back to objects
                if 'data' in event_data:
                    try:
                        event_data['data'] = json.loads(event_data['data'])
                    except (json.JSONDecodeError, TypeError):
                        event_data['data'] = {}

                if 'metadata' in event_data:
                    try:
                        event_data['metadata'] = json.loads(event_data['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        event_data['metadata'] = {}

                if 'processed_by' in event_data:
                    try:
                        event_data['processed_by'] = json.loads(event_data['processed_by'])
                    except (json.JSONDecodeError, TypeError):
                        event_data['processed_by'] = []

                if 'parent_events' in event_data:
                    try:
                        if isinstance(event_data['parent_events'], str):
                            event_data['parent_events'] = json.loads(event_data['parent_events'])
                    except (json.JSONDecodeError, TypeError):
                        event_data['parent_events'] = []

            return event_data

        except Exception as e:
            logger.error(f"Failed to get event {event_id} from Redis: {e}")
            return None

    async def get_conversation_events(self, conversation_id: str,
                                   limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get events for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List[Dict[str, Any]]: List of event data
        """
        try:
            events = await self.redis.get_conversation_events(conversation_id, limit, offset)

            # Parse JSON fields for each event
            for event in events:
                if 'data' in event:
                    try:
                        event['data'] = json.loads(event['data'])
                    except (json.JSONDecodeError, TypeError):
                        event['data'] = {}

                if 'metadata' in event:
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        event['metadata'] = {}

                if 'processed_by' in event:
                    try:
                        event['processed_by'] = json.loads(event['processed_by'])
                    except (json.JSONDecodeError, TypeError):
                        event['processed_by'] = []

                if 'parent_events' in event:
                    try:
                        if isinstance(event['parent_events'], str):
                            event['parent_events'] = json.loads(event['parent_events'])
                    except (json.JSONDecodeError, TypeError):
                        event['parent_events'] = []

            return events

        except Exception as e:
            logger.error(f"Failed to get conversation events from Redis: {e}")
            return []

    async def get_user_events(self, user_id: str,
                            limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get events for a user.

        Args:
            user_id: User ID
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List[Dict[str, Any]]: List of event data
        """
        try:
            events = await self.redis.get_user_events(user_id, limit, offset)

            # Parse JSON fields for each event
            for event in events:
                if 'data' in event:
                    try:
                        event['data'] = json.loads(event['data'])
                    except (json.JSONDecodeError, TypeError):
                        event['data'] = {}

                if 'metadata' in event:
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except (json.JSONDecodeError, TypeError):
                        event['metadata'] = {}

                if 'processed_by' in event:
                    try:
                        event['processed_by'] = json.loads(event['processed_by'])
                    except (json.JSONDecodeError, TypeError):
                        event['processed_by'] = []

                if 'parent_events' in event:
                    try:
                        if isinstance(event['parent_events'], str):
                            event['parent_events'] = json.loads(event['parent_events'])
                    except (json.JSONDecodeError, TypeError):
                        event['parent_events'] = []

            return events

        except Exception as e:
            logger.error(f"Failed to get user events from Redis: {e}")
            return []


# Global Redis persistence instance
redis_persistence = RedisEventPersistence()
