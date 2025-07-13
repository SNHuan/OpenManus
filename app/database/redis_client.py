"""Redis client for event storage."""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

try:
    # For Python 3.12+, use redis-py with asyncio support instead of aioredis
    import redis.asyncio as redis_async
    import redis
    REDIS_AVAILABLE = True
    USE_REDIS_ASYNCIO = True
except ImportError:
    try:
        # Fallback to aioredis if available
        import aioredis
        REDIS_AVAILABLE = True
        USE_REDIS_ASYNCIO = False
    except ImportError as e:
        logger.warning(f"Redis not available: {e}")
        REDIS_AVAILABLE = False
        redis_async = None
        redis = None
        aioredis = None
        USE_REDIS_ASYNCIO = False

from app.logger import logger
from app.settings import settings


class RedisClient:
    """Redis client for event storage and caching."""

    def __init__(self):
        self._redis: Optional[Any] = None
        self._connection_pool = None

    async def connect(self) -> bool:
        """Connect to Redis server."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis libraries not available")
            return False

        try:
            if USE_REDIS_ASYNCIO:
                # Use redis-py asyncio (Python 3.12+ compatible)
                self._redis = redis_async.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    max_connections=20,
                    retry_on_timeout=True
                )
            else:
                # Use aioredis (older Python versions)
                self._connection_pool = aioredis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    max_connections=20,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30
                )

                self._redis = aioredis.Redis(
                    connection_pool=self._connection_pool,
                    decode_responses=True
                )

            # Test connection
            await self._redis.ping()
            logger.info(f"Connected to Redis: {settings.REDIS_URL}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Redis."""
        try:
            if self._redis:
                if USE_REDIS_ASYNCIO:
                    await self._redis.aclose()  # redis-py asyncio uses aclose()
                else:
                    await self._redis.close()   # aioredis uses close()
            if self._connection_pool and not USE_REDIS_ASYNCIO:
                await self._connection_pool.disconnect()
            logger.info("Disconnected from Redis")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")

    @property
    def redis(self) -> Any:
        """Get Redis client instance."""
        if not self._redis:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._redis

    async def store_event(self, event_data: Dict[str, Any]) -> bool:
        """Store event in Redis.

        Args:
            event_data: Event data dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            event_id = event_data.get('id')
            if not event_id:
                logger.error("Event ID is required for storage")
                return False

            # Store event data
            event_key = f"event:{event_id}"
            await self.redis.hset(event_key, mapping=event_data)

            # Set expiration (30 days)
            await self.redis.expire(event_key, 30 * 24 * 3600)

            # Add to conversation timeline if conversation_id exists
            conversation_id = event_data.get('conversation_id')
            if conversation_id:
                timeline_key = f"conversation:{conversation_id}:timeline"
                await self.redis.zadd(
                    timeline_key,
                    {event_id: event_data.get('timestamp', datetime.now().timestamp())}
                )
                # Set expiration for timeline
                await self.redis.expire(timeline_key, 30 * 24 * 3600)

            # Add to user timeline if user_id exists
            user_id = event_data.get('user_id')
            if user_id:
                user_timeline_key = f"user:{user_id}:timeline"
                await self.redis.zadd(
                    user_timeline_key,
                    {event_id: event_data.get('timestamp', datetime.now().timestamp())}
                )
                # Set expiration for user timeline
                await self.redis.expire(user_timeline_key, 30 * 24 * 3600)

            # Add to global event stream
            stream_key = "events:stream"
            await self.redis.zadd(
                stream_key,
                {event_id: event_data.get('timestamp', datetime.now().timestamp())}
            )

            # Keep only recent events in global stream (last 10000)
            await self.redis.zremrangebyrank(stream_key, 0, -10001)

            logger.debug(f"Event {event_id} stored in Redis successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to store event in Redis: {e}")
            return False

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID.

        Args:
            event_id: Event ID

        Returns:
            Optional[Dict[str, Any]]: Event data if found, None otherwise
        """
        try:
            event_key = f"event:{event_id}"
            event_data = await self.redis.hgetall(event_key)

            if event_data:
                # Convert string values back to appropriate types
                if 'timestamp' in event_data:
                    try:
                        event_data['timestamp'] = float(event_data['timestamp'])
                    except (ValueError, TypeError):
                        pass

                return event_data
            return None

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
            timeline_key = f"conversation:{conversation_id}:timeline"

            # Get event IDs from timeline (newest first)
            event_ids = await self.redis.zrevrange(
                timeline_key, offset, offset + limit - 1
            )

            if not event_ids:
                return []

            # Get event data for each ID
            events = []
            for event_id in event_ids:
                event_data = await self.get_event(event_id)
                if event_data:
                    events.append(event_data)

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
            timeline_key = f"user:{user_id}:timeline"

            # Get event IDs from timeline (newest first)
            event_ids = await self.redis.zrevrange(
                timeline_key, offset, offset + limit - 1
            )

            if not event_ids:
                return []

            # Get event data for each ID
            events = []
            for event_id in event_ids:
                event_data = await self.get_event(event_id)
                if event_data:
                    events.append(event_data)

            return events

        except Exception as e:
            logger.error(f"Failed to get user events from Redis: {e}")
            return []


# Global Redis client instance
redis_client = RedisClient()
