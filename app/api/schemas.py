"""Pydantic schemas for API request/response models."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


# Authentication schemas
class UserLogin(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Password")
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: "UserResponse"


# User schemas
class UserBase(BaseModel):
    username: str
    email: str
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None


# Conversation schemas
class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Conversation title")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Conversation metadata")


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle metadata_ field mapping."""
        data = {
            'id': obj.id,
            'user_id': obj.user_id,
            'title': obj.title,
            'status': obj.status,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
            'metadata': obj.metadata_ or {}
        }
        return cls(**data)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, pattern="^(active|paused|closed)$")
    metadata: Optional[Dict[str, Any]] = None


# Message schemas
class MessageSend(BaseModel):
    message: str = Field(..., min_length=1, description="Message content")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for threading")


class MessageResponse(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    role: str
    content: str
    status: str
    data: Dict[str, Any]


# Event schemas
class EventResponse(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    source: Optional[str]
    conversation_id: Optional[str]
    user_id: Optional[str]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    status: str
    processed_by: List[str]
    error_message: Optional[str]


class EventChainResponse(BaseModel):
    events: List[EventResponse]
    total_count: int
    root_event_id: Optional[str]


# Pagination schemas
class PaginationParams(BaseModel):
    limit: int = Field(50, ge=1, le=100, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Number of items to skip")


# Response schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# Statistics schemas
class ConversationStats(BaseModel):
    total_conversations: int
    active_conversations: int
    closed_conversations: int
    total_messages: int
    recent_activity: List[Dict[str, Any]]


class EventStats(BaseModel):
    total_events: int
    events_by_type: Dict[str, int]
    recent_events: List[EventResponse]
    error_rate: float
