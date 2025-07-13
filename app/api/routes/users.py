"""User management routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database, get_current_user
from app.api.schemas import UserResponse, UserUpdate, SuccessResponse, PaginationParams
from app.services.user_service import UserService
from app.database.models import User
from app.logger import logger

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserResponse: Current user's profile data
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile.
    
    Args:
        user_update: Updated user data
        session: Database session
        current_user: Current authenticated user
        
    Returns:
        UserResponse: Updated user profile
        
    Raises:
        HTTPException: If update fails
    """
    user_service = UserService(session)
    
    try:
        # Update profile information
        if user_update.username is not None or user_update.email is not None:
            success = await user_service.update_user_profile(
                user_id=current_user.id,
                username=user_update.username,
                email=user_update.email
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username or email already taken"
                )
        
        # Update preferences
        if user_update.preferences is not None:
            success = await user_service.update_user_preferences(
                user_id=current_user.id,
                preferences=user_update.preferences
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update preferences"
                )
        
        # Get updated user
        updated_user = await user_service.get_user_by_id(current_user.id)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found after update"
            )
        
        logger.info(f"User profile updated: {current_user.username}")
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during profile update"
        )


@router.delete("/me", response_model=SuccessResponse)
async def delete_current_user_account(
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Delete current user's account.
    
    Args:
        session: Database session
        current_user: Current authenticated user
        
    Returns:
        SuccessResponse: Account deletion success message
        
    Raises:
        HTTPException: If deletion fails
    """
    user_service = UserService(session)
    
    try:
        success = await user_service.delete_user(current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete account"
            )
        
        logger.info(f"User account deleted: {current_user.username}")
        return SuccessResponse(
            message="Account deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Account deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during account deletion"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID (admin or self only).
    
    Args:
        user_id: User ID to retrieve
        session: Database session
        current_user: Current authenticated user
        
    Returns:
        UserResponse: User profile data
        
    Raises:
        HTTPException: If user not found or access denied
    """
    # For now, users can only access their own profile
    # In the future, admin roles could be implemented
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    user_service = UserService(session)
    
    try:
        user = await user_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{user_id}/conversations", response_model=List[dict])
async def get_user_conversations(
    user_id: str,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    """Get user's conversations.
    
    Args:
        user_id: User ID
        pagination: Pagination parameters
        session: Database session
        current_user: Current authenticated user
        
    Returns:
        List[dict]: List of user's conversations
        
    Raises:
        HTTPException: If access denied or error occurs
    """
    # Users can only access their own conversations
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    from app.services.conversation_service import ConversationService
    conversation_service = ConversationService(session)
    
    try:
        conversations = await conversation_service.get_user_conversations(
            user_id=user_id,
            limit=pagination.limit,
            offset=pagination.offset
        )
        
        # Convert to dict format for response
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "status": conv.status,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "metadata": conv.metadata_
            }
            for conv in conversations
        ]
        
    except Exception as e:
        logger.error(f"Get user conversations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
