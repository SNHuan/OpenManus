#!/usr/bin/env python3
"""Simple backend startup script for OpenManus."""

import sys
import subprocess
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import logger
from app.settings import settings


def main():
    """Start the backend server."""
    try:
        logger.info("🚀 Starting OpenManus Backend Server...")
        logger.info(f"Host: {settings.HOST}:{settings.PORT}")
        logger.info(f"Debug: {settings.DEBUG}")
        logger.info(f"Database: {settings.DATABASE_URL}")
        
        # Build uvicorn command
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", settings.HOST,
            "--port", str(settings.PORT),
            "--log-level", "info"
        ]
        
        if settings.DEBUG:
            cmd.append("--reload")
        
        logger.info(f"Command: {' '.join(cmd)}")
        
        # Start the server
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
