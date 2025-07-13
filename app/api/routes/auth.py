"""Authentication routes for user login and registration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database, get_current_user
from app.api.schemas import UserLogin, UserRegister, Token, SuccessResponse
from app.services.auth_service import AuthService
from app.logger import logger

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login(
    user_login: UserLogin,
    session: AsyncSession = Depends(get_database)
):
    """Login user and return access token.

    Args:
        user_login: Login credentials
        session: Database session

    Returns:
        Token: Access token and user information

    Raises:
        HTTPException: If login fails
    """
    auth_service = AuthService(session)

    try:
        result = await auth_service.login(user_login.username, user_login.password)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"User logged in: {user_login.username}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )


@router.post("/register", response_model=SuccessResponse)
async def register(
    user_register: UserRegister,
    session: AsyncSession = Depends(get_database)
):
    """Register a new user.

    Args:
        user_register: Registration data
        session: Database session

    Returns:
        SuccessResponse: Registration success message

    Raises:
        HTTPException: If registration fails
    """
    auth_service = AuthService(session)

    try:
        user = await auth_service.register(
            username=user_register.username,
            email=user_register.email,
            password=user_register.password,
            preferences=user_register.preferences
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )

        logger.info(f"User registered: {user_register.username}")
        return SuccessResponse(
            message="User registered successfully",
            data={"user_id": user.id, "username": user.username}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout():
    """Logout user (client-side token removal).

    Returns:
        SuccessResponse: Logout success message
    """
    # In a JWT-based system, logout is typically handled client-side
    # by removing the token. Server-side token blacklisting could be
    # implemented here if needed.

    return SuccessResponse(
        message="Logged out successfully. Please remove the token from client storage."
    )


@router.get("/verify", response_model=SuccessResponse)
async def verify_token(
    session: AsyncSession = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Verify current token and return user info.

    Args:
        session: Database session
        current_user: Current authenticated user

    Returns:
        SuccessResponse: Token verification success with user data
    """
    return SuccessResponse(
        message="Token is valid",
        data={
            "id": current_user.id,  # Changed from user_id to id for frontend compatibility
            "user_id": current_user.id,  # Keep both for backward compatibility
            "username": current_user.username,
            "email": current_user.email,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None
        }
    )
