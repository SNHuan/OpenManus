"""Core event handlers for OpenManus project.

This module implements essential event handlers for logging, monitoring,
error handling, and other system-wide event processing.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque

from app.logger import logger
from app.event.base import BaseEvent, BaseEventHandler
from app.event.types import EventPriority, EventStatus
from app.event.events import SystemErrorEvent, ConversationEvent


class LoggingHandler(BaseEventHandler):
    """Event handler for comprehensive logging of all events."""
    
    name: str = "logging_handler"
    description: str = "Logs all events for debugging and monitoring"
    
    def __init__(self, log_level: str = "INFO", **kwargs):
        super().__init__(**kwargs)
        self.log_level = log_level
    
    async def handle(self, event: BaseEvent) -> bool:
        """Log the event details."""
        try:
            # Basic event info
            log_msg = f"Event: {event.event_type} | ID: {event.event_id}"
            
            # Add source if available
            if event.source:
                log_msg += f" | Source: {event.source}"
            
            # Add conversation context if available
            if hasattr(event, 'conversation_id') and event.conversation_id:
                log_msg += f" | Conversation: {event.conversation_id}"
            
            # Add user context if available
            if hasattr(event, 'user_id') and event.user_id:
                log_msg += f" | User: {event.user_id}"
            
            # Log based on event priority and type
            if event.priority == EventPriority.CRITICAL:
                logger.critical(log_msg)
                logger.critical(f"Event data: {json.dumps(event.data, default=str, indent=2)}")
            elif event.priority == EventPriority.HIGH or "error" in event.event_type:
                logger.error(log_msg)
                logger.error(f"Event data: {json.dumps(event.data, default=str, indent=2)}")
            elif self.log_level == "DEBUG":
                logger.debug(log_msg)
                logger.debug(f"Event data: {json.dumps(event.data, default=str, indent=2)}")
            else:
                logger.info(log_msg)
            
            return True
            
        except Exception as e:
            logger.error(f"LoggingHandler failed to process event {event.event_id}: {str(e)}")
            return False


class MonitoringHandler(BaseEventHandler):
    """Event handler for system monitoring and metrics collection."""
    
    name: str = "monitoring_handler"
    description: str = "Collects metrics and monitors system performance"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.conversation_metrics = defaultdict(dict)
        self.recent_events = deque(maxlen=1000)  # Keep last 1000 events
        self.start_time = datetime.now()
    
    async def handle(self, event: BaseEvent) -> bool:
        """Process event for monitoring purposes."""
        try:
            # Update event counts
            self.event_counts[event.event_type] += 1
            self.event_counts["total"] += 1
            
            # Track errors
            if event.status == EventStatus.FAILED or "error" in event.event_type:
                self.error_counts[event.event_type] += 1
                self.error_counts["total"] += 1
            
            # Track conversation metrics
            if hasattr(event, 'conversation_id') and event.conversation_id:
                conv_id = event.conversation_id
                if conv_id not in self.conversation_metrics:
                    self.conversation_metrics[conv_id] = {
                        "event_count": 0,
                        "start_time": event.timestamp,
                        "last_activity": event.timestamp,
                        "event_types": defaultdict(int)
                    }
                
                self.conversation_metrics[conv_id]["event_count"] += 1
                self.conversation_metrics[conv_id]["last_activity"] = event.timestamp
                self.conversation_metrics[conv_id]["event_types"][event.event_type] += 1
            
            # Keep recent events for analysis
            self.recent_events.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "status": event.status,
                "source": event.source
            })
            
            # Log metrics periodically (every 100 events)
            if self.event_counts["total"] % 100 == 0:
                await self._log_metrics()
            
            return True
            
        except Exception as e:
            logger.error(f"MonitoringHandler failed to process event {event.event_id}: {str(e)}")
            return False
    
    async def _log_metrics(self):
        """Log current metrics."""
        uptime = datetime.now() - self.start_time
        
        metrics = {
            "uptime_seconds": uptime.total_seconds(),
            "total_events": self.event_counts["total"],
            "total_errors": self.error_counts["total"],
            "active_conversations": len(self.conversation_metrics),
            "top_event_types": dict(sorted(self.event_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }
        
        logger.info(f"System metrics: {json.dumps(metrics, default=str, indent=2)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current monitoring metrics."""
        uptime = datetime.now() - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "event_counts": dict(self.event_counts),
            "error_counts": dict(self.error_counts),
            "conversation_metrics": dict(self.conversation_metrics),
            "recent_events": list(self.recent_events)
        }


class ErrorHandler(BaseEventHandler):
    """Event handler for system error processing and alerting."""
    
    name: str = "error_handler"
    description: str = "Handles system error events and alerts"
    supported_events: List[str] = ["system.error", "agent.error", "tool.error"]
    priority: int = 100  # High priority for error handling
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.error_history = deque(maxlen=500)  # Keep last 500 errors
        self.error_patterns = defaultdict(int)
    
    async def handle(self, event: BaseEvent) -> bool:
        """Handle system errors."""
        try:
            if isinstance(event, SystemErrorEvent):
                await self._handle_system_error(event)
            elif "error" in event.event_type or event.status == EventStatus.FAILED:
                await self._handle_general_error(event)
            
            # Store error for analysis
            error_record = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "error_data": event.data,
                "conversation_id": getattr(event, 'conversation_id', None)
            }
            self.error_history.append(error_record)
            
            # Track error patterns
            error_key = f"{event.event_type}:{event.data.get('error_type', 'unknown')}"
            self.error_patterns[error_key] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"ErrorHandler failed to process event {event.event_id}: {str(e)}")
            return False
    
    async def _handle_system_error(self, event: SystemErrorEvent):
        """Handle system error events."""
        component = event.data.get("component", "unknown")
        error_type = event.data.get("error_type", "unknown")
        error_message = event.data.get("error_message", "")
        context = event.data.get("context", {})
        
        logger.error(f"System error in {component} [{error_type}]: {error_message}")
        if context:
            logger.error(f"Error context: {json.dumps(context, default=str, indent=2)}")
        
        # TODO: Implement alerting logic here
        # - Send notifications for critical errors
        # - Trigger recovery procedures
        # - Update error metrics
    
    async def _handle_general_error(self, event: BaseEvent):
        """Handle general error events."""
        logger.error(f"Error event: {event.event_type} | Status: {event.status}")
        logger.error(f"Error details: {json.dumps(event.data, default=str, indent=2)}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary and patterns."""
        return {
            "total_errors": len(self.error_history),
            "error_patterns": dict(self.error_patterns),
            "recent_errors": list(self.error_history)[-10:] if self.error_history else []
        }


class ConversationHandler(BaseEventHandler):
    """Event handler for conversation-specific processing."""
    
    name: str = "conversation_handler"
    description: str = "Handles conversation lifecycle events"
    supported_events: List[str] = [
        "conversation.created", "conversation.closed", 
        "user.input", "agent.response", "interrupt"
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_conversations = {}
        self.conversation_history = defaultdict(list)
    
    async def handle(self, event: BaseEvent) -> bool:
        """Handle conversation events."""
        try:
            if not hasattr(event, 'conversation_id') or not event.conversation_id:
                return True  # Skip non-conversation events
            
            conv_id = event.conversation_id
            
            # Update conversation tracking
            if event.event_type == "conversation.created":
                await self._handle_conversation_created(event)
            elif event.event_type == "conversation.closed":
                await self._handle_conversation_closed(event)
            elif event.event_type == "user.input":
                await self._handle_user_input(event)
            elif event.event_type == "agent.response":
                await self._handle_agent_response(event)
            elif event.event_type == "interrupt":
                await self._handle_interrupt(event)
            
            # Add to conversation history
            self.conversation_history[conv_id].append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "data": event.data
            })
            
            return True
            
        except Exception as e:
            logger.error(f"ConversationHandler failed to process event {event.event_id}: {str(e)}")
            return False
    
    async def _handle_conversation_created(self, event: BaseEvent):
        """Handle conversation creation."""
        conv_id = event.conversation_id
        user_id = getattr(event, 'user_id', None)
        
        self.active_conversations[conv_id] = {
            "user_id": user_id,
            "created_at": event.timestamp,
            "last_activity": event.timestamp,
            "message_count": 0,
            "status": "active"
        }
        
        logger.info(f"New conversation created: {conv_id} for user: {user_id}")
    
    async def _handle_conversation_closed(self, event: BaseEvent):
        """Handle conversation closure."""
        conv_id = event.conversation_id
        
        if conv_id in self.active_conversations:
            self.active_conversations[conv_id]["status"] = "closed"
            self.active_conversations[conv_id]["closed_at"] = event.timestamp
        
        logger.info(f"Conversation closed: {conv_id}")
    
    async def _handle_user_input(self, event: BaseEvent):
        """Handle user input."""
        conv_id = event.conversation_id
        
        if conv_id in self.active_conversations:
            self.active_conversations[conv_id]["message_count"] += 1
            self.active_conversations[conv_id]["last_activity"] = event.timestamp
    
    async def _handle_agent_response(self, event: BaseEvent):
        """Handle agent response."""
        conv_id = event.conversation_id
        
        if conv_id in self.active_conversations:
            self.active_conversations[conv_id]["last_activity"] = event.timestamp
    
    async def _handle_interrupt(self, event: BaseEvent):
        """Handle conversation interrupt."""
        conv_id = event.conversation_id
        
        if conv_id in self.active_conversations:
            self.active_conversations[conv_id]["last_activity"] = event.timestamp
        
        logger.info(f"Conversation interrupted: {conv_id}")
    
    def get_conversation_info(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific conversation."""
        return self.active_conversations.get(conversation_id)
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get event history for a conversation."""
        return self.conversation_history.get(conversation_id, [])
