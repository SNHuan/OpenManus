"""FastAPI dependencies for authentication and database access."""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_database as get_db_session
from app.database.models import User
from app.services.auth_service import AuthService

# Security scheme
security = HTTPBearer()


async def get_database() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_database)
) -> User:
    """Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        session: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_service = AuthService(session)
    
    try:
        user = await auth_service.get_current_user(credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_database)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.
    
    Args:
        credentials: Optional HTTP Bearer token credentials
        session: Database session
        
    Returns:
        Optional[User]: Current user if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    auth_service = AuthService(session)
    
    try:
        return await auth_service.get_current_user(credentials.credentials)
    except Exception:
        return None
