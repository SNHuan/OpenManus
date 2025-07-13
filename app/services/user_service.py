"""User service for user management operations."""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.logger import logger
from app.database.models import User, Conversation
from app.database.database import AsyncSessionLocal


class UserService:
    """Service for user management operations."""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session
    
    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        return AsyncSessionLocal()
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                return user
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to get user by ID {user_id}: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = select(User).where(User.username == username)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                return user
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            Optional[User]: User object if found, None otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = select(User).where(User.email == email)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                return user
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None
    
    async def get_user_with_conversations(self, user_id: str) -> Optional[User]:
        """Get user with their conversations.
        
        Args:
            user_id: User ID
            
        Returns:
            Optional[User]: User object with conversations loaded
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = (
                    select(User)
                    .options(selectinload(User.conversations))
                    .where(User.id == user_id)
                )
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                return user
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to get user with conversations {user_id}: {e}")
            return None
    
    async def update_user_preferences(self, user_id: str, 
                                    preferences: Dict[str, Any]) -> bool:
        """Update user preferences.
        
        Args:
            user_id: User ID
            preferences: New preferences dictionary
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = (
                    update(User)
                    .where(User.id == user_id)
                    .values(preferences=preferences)
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Updated preferences for user {user_id}")
                    return True
                else:
                    logger.warning(f"No user found to update preferences: {user_id}")
                    return False
                    
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to update user preferences {user_id}: {e}")
            return False
    
    async def update_user_profile(self, user_id: str, 
                                username: Optional[str] = None,
                                email: Optional[str] = None) -> bool:
        """Update user profile information.
        
        Args:
            user_id: User ID
            username: New username (optional)
            email: New email (optional)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                # Build update values
                update_values = {}
                if username is not None:
                    # Check if username is already taken
                    existing = await self.get_user_by_username(username)
                    if existing and existing.id != user_id:
                        logger.warning(f"Username already taken: {username}")
                        return False
                    update_values["username"] = username
                
                if email is not None:
                    # Check if email is already taken
                    existing = await self.get_user_by_email(email)
                    if existing and existing.id != user_id:
                        logger.warning(f"Email already taken: {email}")
                        return False
                    update_values["email"] = email
                
                if not update_values:
                    return True  # Nothing to update
                
                stmt = (
                    update(User)
                    .where(User.id == user_id)
                    .values(**update_values)
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Updated profile for user {user_id}")
                    return True
                else:
                    logger.warning(f"No user found to update profile: {user_id}")
                    return False
                    
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to update user profile {user_id}: {e}")
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and all associated data.
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                # Delete user (cascading will handle conversations and events)
                stmt = delete(User).where(User.id == user_id)
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Deleted user {user_id}")
                    return True
                else:
                    logger.warning(f"No user found to delete: {user_id}")
                    return False
                    
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            return False
    
    async def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List users with pagination.
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List[User]: List of users
        """
        try:
            session = await self._get_session()
            close_session = self._session is None
            
            try:
                stmt = (
                    select(User)
                    .order_by(User.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                users = result.scalars().all()
                
                return list(users)
            finally:
                if close_session:
                    await session.close()
                    
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []
