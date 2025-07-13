"""Event bus system for OpenManus project.

This module provides a lightweight event-driven architecture that allows
components to communicate through events without tight coupling.
"""

from .base import BaseEvent, BaseEventHandler, BaseEventBus
from .bus import EventBus
from .types import EventPriority, EventStatus
from .events import (
    ConversationCreatedEvent, ConversationClosedEvent, UserInputEvent, InterruptEvent,
    AgentStepStartEvent, AgentStepCompleteEvent, AgentResponseEvent, LLMStreamEvent,
    ToolExecutionEvent, ToolResultEvent, ToolResultDisplayEvent, SystemErrorEvent,
    ToolExecutionStatus, AgentState, DataOperationType,
    create_conversation_created_event, create_user_input_event, create_interrupt_event,
    create_agent_step_start_event, create_tool_execution_event, create_system_error_event
)
from .manager import EventBusManager, event_manager, EventAwareMixin, event_publisher, event_context
from .handlers import LoggingHandler, MonitoringHandler, ErrorHandler, ConversationHandler

__all__ = [
    # Base classes
    "BaseEvent",
    "BaseEventHandler",
    "BaseEventBus",
    "EventBus",
    "EventPriority",
    "EventStatus",

    # Concrete events
    "ConversationCreatedEvent",
    "ConversationClosedEvent",
    "UserInputEvent",
    "InterruptEvent",
    "AgentStepStartEvent",
    "AgentStepCompleteEvent",
    "AgentResponseEvent",
    "LLMStreamEvent",
    "ToolExecutionEvent",
    "ToolResultEvent",
    "ToolResultDisplayEvent",
    "SystemErrorEvent",

    # Enums
    "ToolExecutionStatus",
    "AgentState",
    "DataOperationType",

    # Event factory functions
    "create_conversation_created_event",
    "create_user_input_event",
    "create_interrupt_event",
    "create_agent_step_start_event",
    "create_tool_execution_event",
    "create_system_error_event",

    # Manager and integration
    "EventBusManager",
    "event_manager",
    "EventAwareMixin",
    "event_publisher",
    "event_context",

    # Handlers
    "LoggingHandler",
    "MonitoringHandler",
    "ErrorHandler",
    "ConversationHandler",
]
