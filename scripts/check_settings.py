#!/usr/bin/env python3
"""Check current settings values."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.settings import settings

def main():
    """Check settings."""
    print("🔍 Current Settings:")
    print(f"EVENT_PERSISTENCE_ENABLED: {settings.EVENT_PERSISTENCE_ENABLED}")
    print(f"EVENT_TRACKING_ENABLED: {settings.EVENT_TRACKING_ENABLED}")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"DEBUG: {settings.DEBUG}")
    
    # Check environment variables
    import os
    print(f"\n🌍 Environment Variables:")
    print(f"EVENT_PERSISTENCE_ENABLED: {os.getenv('EVENT_PERSISTENCE_ENABLED', 'NOT SET')}")
    print(f"EVENT_TRACKING_ENABLED: {os.getenv('EVENT_TRACKING_ENABLED', 'NOT SET')}")

if __name__ == "__main__":
    main()
