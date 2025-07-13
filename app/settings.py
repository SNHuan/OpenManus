"""Settings and configuration for the multi-user conversation system."""

import os
import json
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings for the multi-user conversation system."""

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./openmanus.db")

    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_EVENT_EXPIRY: int = int(os.getenv("REDIS_EVENT_EXPIRY", "2592000"))  # 30 days

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS Configuration
    @property
    def CORS_ORIGINS(self) -> List[str]:
        cors_origins = os.getenv("CORS_ORIGINS", '["http://localhost:3000"]')
        if isinstance(cors_origins, str):
            try:
                return json.loads(cors_origins)
            except json.JSONDecodeError:
                return ["http://localhost:3000"]
        return cors_origins

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Agent Configuration
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "300"))
    AGENT_MAX_STEPS: int = int(os.getenv("AGENT_MAX_STEPS", "50"))

    # Event System Configuration
    EVENT_PERSISTENCE_ENABLED: bool = os.getenv("EVENT_PERSISTENCE_ENABLED", "true").lower() == "true"
    EVENT_TRACKING_ENABLED: bool = os.getenv("EVENT_TRACKING_ENABLED", "true").lower() == "true"

    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    WS_MAX_CONNECTIONS: int = int(os.getenv("WS_MAX_CONNECTIONS", "100"))

    # Frontend Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Security Settings
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Development Settings
    RELOAD_ON_CHANGE: bool = os.getenv("RELOAD_ON_CHANGE", "false").lower() == "true"
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() == "true"

    # Optional API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        errors = []

        # Check required settings
        if cls.SECRET_KEY == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY must be changed from default value")

        if len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY should be at least 32 characters long")

        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")

        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True

    @classmethod
    def print_config(cls) -> None:
        """Print current configuration (excluding sensitive data)."""
        print("OpenManus Multi-User System Configuration:")
        print(f"  Database: {cls.DATABASE_URL}")
        print(f"  Host: {cls.HOST}:{cls.PORT}")
        print(f"  Debug: {cls.DEBUG}")
        print(f"  CORS Origins: {cls().CORS_ORIGINS}")
        print(f"  Log Level: {cls.LOG_LEVEL}")
        print(f"  Agent Timeout: {cls.AGENT_TIMEOUT}s")
        print(f"  Event Persistence: {cls.EVENT_PERSISTENCE_ENABLED}")
        print(f"  WebSocket Max Connections: {cls.WS_MAX_CONNECTIONS}")
        print(f"  Frontend URL: {cls.FRONTEND_URL}")
        print(f"  Docs Enabled: {cls.ENABLE_DOCS}")


# Global settings instance
settings = Settings()

# Validate configuration on import
if not settings.validate():
    print("Warning: Configuration validation failed!")
    print("Please check your .env file or environment variables.")
