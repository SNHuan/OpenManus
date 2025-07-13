"""Database models for OpenManus project."""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, JSON, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.database import Base


class User(Base):
    """User model for authentication and user management."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # User credentials
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # User preferences
    preferences: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_username", "username"),
        Index("idx_email", "email"),
    )


class Conversation(Base):
    """Conversation model for managing user conversations."""

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False
    )

    # Conversation details
    title: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(20),
        default="active"
    )  # active, paused, closed

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_conversation_user_id", "user_id"),
        Index("idx_conversation_status", "status"),
        Index("idx_conversation_created_at", "created_at"),
    )


class Event(Base):
    """Event model for storing all system events."""

    __tablename__ = "events"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # Event type and source
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # Foreign keys
    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("conversations.id")
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(36))
    session_id: Mapped[Optional[str]] = mapped_column(String(36))

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Event relationships
    parent_events: Mapped[Optional[List[str]]] = mapped_column(JSON)
    root_event_id: Mapped[Optional[str]] = mapped_column(String(36))

    # Event data
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending"
    )
    processed_by: Mapped[Optional[List[str]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
        back_populates="events"
    )

    # Indexes
    __table_args__ = (
        Index("idx_event_conversation_id", "conversation_id"),
        Index("idx_event_user_id", "user_id"),
        Index("idx_event_timestamp", "timestamp"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_status", "status"),
        Index("idx_event_root_event_id", "root_event_id"),
    )
