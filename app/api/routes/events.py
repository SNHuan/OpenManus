"""Event management and tracing routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database, get_current_user
from app.api.schemas import EventResponse, EventChainResponse, PaginationParams
from app.event.manager import event_manager
from app.database.models import User
from app.logger import logger

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get event by ID.

    Args:
        event_id: Event ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        EventResponse: Event data

    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        event = await event_manager.get_event(event_id)

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Check if user has access to this event
        # Users can only access events from their own conversations
        if hasattr(event, 'user_id') and event.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # If event has conversation_id, verify user owns the conversation
        if hasattr(event, 'conversation_id') and event.conversation_id:
            from app.services.conversation_service import ConversationService
            conversation_service = ConversationService(session)
            conversation = await conversation_service.get_conversation(event.conversation_id)
            
            if not conversation or conversation.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        return EventResponse(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            source=event.source,
            conversation_id=getattr(event, 'conversation_id', None),
            user_id=getattr(event, 'user_id', None),
            data=event.data,
            metadata=event.metadata,
            status=event.status.value,
            processed_by=event.processed_by,
            error_message=event.error_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get event error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{event_id}/trace", response_model=EventChainResponse)
async def get_event_trace(
    event_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get event trace/chain.

    Args:
        event_id: Event ID to trace
        session: Database session
        current_user: Current authenticated user

    Returns:
        EventChainResponse: Event chain data

    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        # First verify user has access to the event
        event = await event_manager.get_event(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Check access permissions
        if hasattr(event, 'user_id') and event.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        if hasattr(event, 'conversation_id') and event.conversation_id:
            from app.services.conversation_service import ConversationService
            conversation_service = ConversationService(session)
            conversation = await conversation_service.get_conversation(event.conversation_id)
            
            if not conversation or conversation.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        # Get event chain
        event_chain = await event_manager.get_event_chain(event_id)

        # Convert to response format
        event_responses = []
        for evt in event_chain:
            event_responses.append(EventResponse(
                event_id=evt.event_id,
                event_type=evt.event_type,
                timestamp=evt.timestamp,
                source=evt.source,
                conversation_id=getattr(evt, 'conversation_id', None),
                user_id=getattr(evt, 'user_id', None),
                data=evt.data,
                metadata=evt.metadata,
                status=evt.status.value,
                processed_by=evt.processed_by,
                error_message=evt.error_message
            ))

        return EventChainResponse(
            events=event_responses,
            total_count=len(event_responses),
            root_event_id=getattr(event, 'root_event_id', None)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get event trace error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{event_id}/related", response_model=List[EventResponse])
async def get_related_events(
    event_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get events related to the given event.

    Args:
        event_id: Event ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        List[EventResponse]: List of related events

    Raises:
        HTTPException: If event not found or access denied
    """
    try:
        # First verify user has access to the event
        event = await event_manager.get_event(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Check access permissions (same as above)
        if hasattr(event, 'user_id') and event.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        if hasattr(event, 'conversation_id') and event.conversation_id:
            from app.services.conversation_service import ConversationService
            conversation_service = ConversationService(session)
            conversation = await conversation_service.get_conversation(event.conversation_id)
            
            if not conversation or conversation.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

        # Get related events
        related_events = await event_manager.get_related_events(event_id)

        # Convert to response format
        return [
            EventResponse(
                event_id=evt.event_id,
                event_type=evt.event_type,
                timestamp=evt.timestamp,
                source=evt.source,
                conversation_id=getattr(evt, 'conversation_id', None),
                user_id=getattr(evt, 'user_id', None),
                data=evt.data,
                metadata=evt.metadata,
                status=evt.status.value,
                processed_by=evt.processed_by,
                error_message=evt.error_message
            )
            for evt in related_events
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get related events error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
