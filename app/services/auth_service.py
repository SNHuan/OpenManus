"""Authentication service for user management."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.logger import logger
from app.database.models import User
from app.database.database import get_database
from app.settings import settings


# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# JWT settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


class AuthService:
    """Authentication service for user login and token management."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def _get_session(self) -> tuple[AsyncSession, bool]:
        """Get database session and whether it should be closed.

        Returns:
            tuple[AsyncSession, bool]: (session, should_close)
        """
        if self._session:
            return self._session, False
        # For non-dependency injection usage, create a new session
        from app.database.database import AsyncSessionLocal
        return AsyncSessionLocal(), True

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            Optional[User]: User object if authentication successful, None otherwise
        """
        try:
            session, close_session = await self._get_session()

            # Try to find user by username or email
            stmt = select(User).where(
                (User.username == username) | (User.email == username)
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"Authentication failed: user not found - {username}")
                return None

            if not self.verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: invalid password - {username}")
                return None

            # Update last login
            user.last_login = datetime.now()
            await session.commit()

            logger.info(f"User authenticated successfully: {user.username}")
            return user

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
        finally:
            if close_session and session:
                await session.close()

    def create_access_token(self, data: Dict[str, Any],
                          expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time

        Returns:
            str: JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Optional[Dict[str, Any]]: Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from JWT token.

        Args:
            token: JWT token

        Returns:
            Optional[User]: User object if token is valid, None otherwise
        """
        try:
            payload = self.verify_token(token)
            if not payload:
                return None

            user_id = payload.get("sub")
            if not user_id:
                return None

            session, close_session = await self._get_session()
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            return user

        except Exception as e:
            logger.error(f"Get current user error: {e}")
            return None
        finally:
            if 'close_session' in locals() and close_session and 'session' in locals() and session:
                await session.close()

    async def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Login user and return token.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            Optional[Dict[str, Any]]: Login response with token and user info
        """
        user = await self.authenticate_user(username, password)
        if not user:
            return None

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user.id, "username": user.username},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "preferences": user.preferences or {}
            }
        }

    async def register(self, username: str, email: str, password: str,
                      preferences: Optional[Dict[str, Any]] = None) -> Optional[User]:
        """Register a new user.

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password
            preferences: Optional user preferences

        Returns:
            Optional[User]: Created user object if successful, None otherwise
        """
        try:
            session, close_session = await self._get_session()

            # Check if username or email already exists
            stmt = select(User).where(
                (User.username == username) | (User.email == email)
            )
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                if existing_user.username == username:
                    logger.warning(f"Registration failed: username already exists - {username}")
                else:
                    logger.warning(f"Registration failed: email already exists - {email}")
                return None

            # Create new user
            hashed_password = self.get_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                preferences=preferences or {}
            )

            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            logger.info(f"User registered successfully: {username}")
            return new_user

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None
        finally:
            if close_session and session:
                await session.close()
