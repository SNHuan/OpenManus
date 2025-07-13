"""Database configuration and connection management."""

import os
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from dotenv import load_dotenv

from app.logger import logger
from app.settings import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    metadata = MetaData()


# Database configuration
DATABASE_URL = settings.DATABASE_URL

# Create async engine with SQLite-specific optimizations
if "sqlite" in DATABASE_URL:
    # SQLite-specific configuration with better connection management
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        future=True,
        pool_timeout=5,  # Reduced timeout for faster failure
        pool_recycle=300,  # Recycle connections every 5 minutes
        pool_size=5,  # Allow multiple connections for better concurrency
        max_overflow=10,  # Allow overflow connections
        pool_pre_ping=True,  # Verify connections before use
        connect_args={
            "check_same_thread": False,
            "timeout": 5,  # Reduced SQLite timeout
        }
    )
else:
    # PostgreSQL/MySQL configuration
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_timeout=20,
        pool_recycle=3600,  # Recycle connections every hour
        pool_size=5,
        max_overflow=10,
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_database():
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            # Import models to ensure they are registered
            from app.database.models import User, Conversation, Event

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
