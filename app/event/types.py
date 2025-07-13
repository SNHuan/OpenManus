"""Event system type definitions."""

from enum import Enum
from typing import Literal


class EventPriority(str, Enum):
    """Event priority levels for processing order."""
    
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, Enum):
    """Event processing status."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Type aliases for better type hints
EVENT_PRIORITY_VALUES = tuple(priority.value for priority in EventPriority)
EVENT_PRIORITY_TYPE = Literal[EVENT_PRIORITY_VALUES]  # type: ignore

EVENT_STATUS_VALUES = tuple(status.value for status in EventStatus)  
EVENT_STATUS_TYPE = Literal[EVENT_STATUS_VALUES]  # type: ignore
