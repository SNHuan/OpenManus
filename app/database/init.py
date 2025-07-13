"""Database initialization and setup utilities."""

import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.database.database import init_database, get_database
from app.database.models import User, Conversation, Event
from app.event.manager import event_manager
from app.event.persistence_handler import (
    PersistenceEventHandler,
    ConversationEventHandler,
    SystemMonitoringHandler
)
from app.websocket.handlers import ConversationWebSocketHandler
from app.event.agent_handler import AgentEventHandler, InterruptEventHandler


async def setup_database():
    """Initialize database tables and setup."""
    try:
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialization completed")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


async def setup_event_system():
    """Initialize event system with Redis persistence."""
    try:
        logger.info("Initializing event system...")

        # Initialize event manager first (always succeeds)
        from app.settings import settings
        await event_manager.initialize(enable_persistence=settings.EVENT_PERSISTENCE_ENABLED)

        # Try to initialize Redis connection
        redis_connected = False
        try:
            from app.database.redis_client import redis_client, REDIS_AVAILABLE

            if REDIS_AVAILABLE:
                redis_connected = await redis_client.connect()

                if redis_connected:
                    logger.info("Redis connected successfully for event storage")
                else:
                    logger.warning("Redis connection failed, using SQLite for events")
            else:
                logger.info("Redis libraries not available, using SQLite for events")

        except Exception as redis_error:
            logger.warning(f"Redis initialization failed: {redis_error}, using SQLite for events")
            redis_connected = False

        # Register event handlers (Redis + SQLite hybrid)
        await register_hybrid_handlers(use_redis=redis_connected)

        logger.info("Event system initialization completed")
        return True
    except Exception as e:
        logger.error(f"Event system initialization failed: {e}")
        return False


async def register_hybrid_handlers(use_redis: bool = True):
    """Register hybrid event handlers (Redis + SQLite)."""
    try:
        # Register persistence handler based on availability
        if use_redis:
            from app.event.redis_persistence_handler import RedisPersistenceHandler
            persistence_handler = RedisPersistenceHandler()
            await event_manager.subscribe(persistence_handler)
            logger.info("Redis persistence handler registered")
        else:
            persistence_handler = PersistenceEventHandler()
            await event_manager.subscribe(persistence_handler)
            logger.info("SQLite persistence handler registered")

        # Register other handlers
        conversation_handler = ConversationEventHandler()
        await event_manager.subscribe(conversation_handler)

        monitoring_handler = SystemMonitoringHandler()
        await event_manager.subscribe(monitoring_handler)

        websocket_handler = ConversationWebSocketHandler()
        await event_manager.subscribe(websocket_handler)

        agent_handler = AgentEventHandler()
        await event_manager.subscribe(agent_handler)

        interrupt_handler = InterruptEventHandler()
        await event_manager.subscribe(interrupt_handler)

        logger.info("Hybrid event handlers registered")
        return True
    except Exception as e:
        logger.error(f"Failed to register hybrid handlers: {e}")
        return False


async def register_default_handlers():
    """Register default event handlers."""
    try:
        # Register persistence handler
        persistence_handler = PersistenceEventHandler()
        await event_manager.subscribe(persistence_handler)

        # Register conversation handler
        conversation_handler = ConversationEventHandler()
        await event_manager.subscribe(conversation_handler)

        # Register monitoring handler
        monitoring_handler = SystemMonitoringHandler()
        await event_manager.subscribe(monitoring_handler)

        # Register WebSocket handler
        websocket_handler = ConversationWebSocketHandler()
        await event_manager.subscribe(websocket_handler)

        # Register agent handlers
        agent_handler = AgentEventHandler()
        await event_manager.subscribe(agent_handler)

        interrupt_handler = InterruptEventHandler()
        await event_manager.subscribe(interrupt_handler)

        logger.info("Default event handlers registered")

    except Exception as e:
        logger.error(f"Failed to register default handlers: {e}")
        raise


async def create_test_data():
    """Create test data for development."""
    try:
        async for session in get_database():
            # Create test user
            test_user = User(
                username="testuser",
                email="test@example.com",
                password_hash="$2b$12$dummy_hash_for_testing",
                preferences={"theme": "dark", "language": "en"}
            )

            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            # Create test conversation
            test_conversation = Conversation(
                user_id=test_user.id,
                title="Test Conversation",
                status="active",
                metadata_={"created_by": "init_script"}
            )

            session.add(test_conversation)
            await session.commit()

            logger.info(f"Test data created - User: {test_user.id}, Conversation: {test_conversation.id}")
            return test_user.id, test_conversation.id

    except Exception as e:
        logger.error(f"Failed to create test data: {e}")
        return None, None


async def verify_setup():
    """Verify that the setup was successful."""
    try:
        # Test database connection
        async for session in get_database():
            # Test basic query
            from sqlalchemy import select
            result = await session.execute(select(User).limit(1))
            user = result.scalar_one_or_none()

            if user:
                logger.info(f"Database verification successful - Found user: {user.username}")
            else:
                logger.info("Database verification successful - No users found (empty database)")

        # Test event system
        from app.event.events import create_system_error_event
        test_event = create_system_error_event(
            component="init_script",
            error_type="test",
            error_message="This is a test event"
        )

        success = await event_manager.publish(test_event)
        if success:
            logger.info("Event system verification successful")
        else:
            logger.warning("Event system verification failed")

        return True

    except Exception as e:
        logger.error(f"Setup verification failed: {e}")
        return False


async def full_setup(create_test: bool = False):
    """Perform full system setup.

    Args:
        create_test: Whether to create test data

    Returns:
        bool: True if setup was successful
    """
    logger.info("Starting full system setup...")

    # Setup database
    if not await setup_database():
        return False

    # Setup event system
    if not await setup_event_system():
        return False

    # Create test data if requested
    if create_test:
        user_id, conv_id = await create_test_data()
        if user_id and conv_id:
            logger.info("Test data creation completed")
        else:
            logger.warning("Test data creation failed")

    # Verify setup
    if await verify_setup():
        logger.info("Full system setup completed successfully")
        return True
    else:
        logger.error("Setup verification failed")
        return False


async def cleanup():
    """Cleanup resources."""
    try:
        await event_manager.shutdown()
        logger.info("System cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    async def main():
        success = await full_setup(create_test=True)
        if success:
            logger.info("Setup completed successfully")
        else:
            logger.error("Setup failed")

        await cleanup()

    asyncio.run(main())
