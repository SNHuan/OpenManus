"""Conversation management routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database, get_current_user
from app.api.schemas import (
    ConversationCreate, ConversationResponse, ConversationUpdate,
    MessageSend, MessageResponse, SuccessResponse, PaginationParams
)
from app.services.conversation_service import ConversationService
from app.database.models import User
from app.logger import logger

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    conversation_data: ConversationCreate,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Create a new conversation.

    Args:
        conversation_data: Conversation creation data
        session: Database session
        current_user: Current authenticated user

    Returns:
        ConversationResponse: Created conversation data

    Raises:
        HTTPException: If creation fails
    """
    conversation_service = ConversationService(session)

    try:
        conversation = await conversation_service.create_conversation(
            user_id=current_user.id,
            title=conversation_data.title,
            metadata=conversation_data.metadata
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create conversation"
            )

        logger.info(f"Conversation created: {conversation.id} for user {current_user.username}")
        return ConversationResponse.from_orm(conversation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during conversation creation"
        )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get conversation by ID.

    Args:
        conversation_id: Conversation ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        ConversationResponse: Conversation data

    Raises:
        HTTPException: If conversation not found or access denied
    """
    conversation_service = ConversationService(session)

    try:
        conversation = await conversation_service.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # Check if user has access to this conversation
        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return ConversationResponse.from_orm(conversation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    conversation_update: ConversationUpdate,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Update conversation.

    Args:
        conversation_id: Conversation ID
        conversation_update: Updated conversation data
        session: Database session
        current_user: Current authenticated user

    Returns:
        ConversationResponse: Updated conversation data

    Raises:
        HTTPException: If update fails or access denied
    """
    conversation_service = ConversationService(session)

    try:
        # Verify conversation exists and user has access
        conversation = await conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Update conversation
        success = await conversation_service.update_conversation(
            conversation_id=conversation_id,
            title=conversation_update.title,
            status=conversation_update.status,
            metadata=conversation_update.metadata
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update conversation"
            )

        # Get updated conversation
        updated_conversation = await conversation_service.get_conversation(conversation_id)

        logger.info(f"Conversation updated: {conversation_id}")
        return ConversationResponse.from_orm(updated_conversation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during conversation update"
        )


@router.delete("/{conversation_id}", response_model=SuccessResponse)
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Delete conversation.

    Args:
        conversation_id: Conversation ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        SuccessResponse: Deletion success message

    Raises:
        HTTPException: If deletion fails or access denied
    """
    conversation_service = ConversationService(session)

    try:
        # Verify conversation exists and user has access
        conversation = await conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Delete conversation
        success = await conversation_service.delete_conversation(conversation_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete conversation"
            )

        logger.info(f"Conversation deleted: {conversation_id}")
        return SuccessResponse(
            message="Conversation deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during conversation deletion"
        )


@router.post("/{conversation_id}/messages", response_model=SuccessResponse)
async def send_message(
    conversation_id: str,
    message_data: MessageSend,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Send a message in a conversation.

    Args:
        conversation_id: Conversation ID
        message_data: Message data
        session: Database session
        current_user: Current authenticated user

    Returns:
        SuccessResponse: Message sent confirmation with event ID

    Raises:
        HTTPException: If sending fails or access denied
    """
    conversation_service = ConversationService(session)

    try:
        event_id = await conversation_service.send_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=message_data.message,
            parent_event_id=message_data.parent_event_id
        )

        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send message"
            )

        logger.info(f"Message sent in conversation {conversation_id}")
        return SuccessResponse(
            message="Message sent successfully",
            data={"event_id": event_id}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during message sending"
        )


@router.post("/{conversation_id}/interrupt", response_model=SuccessResponse)
async def interrupt_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Interrupt an ongoing conversation.

    Args:
        conversation_id: Conversation ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        SuccessResponse: Interrupt confirmation

    Raises:
        HTTPException: If interrupt fails or access denied
    """
    conversation_service = ConversationService(session)

    try:
        success = await conversation_service.interrupt_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to interrupt conversation"
            )

        logger.info(f"Conversation {conversation_id} interrupted")
        return SuccessResponse(
            message="Conversation interrupted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Interrupt conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during conversation interrupt"
        )


@router.get("/{conversation_id}/history", response_model=List[MessageResponse])
async def get_conversation_history(
    conversation_id: str,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get conversation message history.

    Args:
        conversation_id: Conversation ID
        pagination: Pagination parameters
        session: Database session
        current_user: Current authenticated user

    Returns:
        List[MessageResponse]: List of conversation messages

    Raises:
        HTTPException: If access denied or error occurs
    """
    conversation_service = ConversationService(session)

    try:
        messages = await conversation_service.get_conversation_history(
            conversation_id=conversation_id,
            user_id=current_user.id,
            limit=pagination.limit,
            offset=pagination.offset
        )

        # Convert to MessageResponse format
        return [
            MessageResponse(
                event_id=msg["event_id"],
                event_type=msg["event_type"],
                timestamp=msg["timestamp"],
                role=msg["role"],
                content=msg["content"],
                status=msg["status"],
                data=msg["data"]
            )
            for msg in messages
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
