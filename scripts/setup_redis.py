#!/usr/bin/env python3
"""Setup Redis for OpenManus project."""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import logger


async def install_redis_dependencies():
    """Install Redis Python dependencies."""
    try:
        logger.info("Installing Redis dependencies...")
        
        # Install Redis dependencies
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "redis>=5.0.1", "aioredis>=2.0.1"
        ], check=True)
        
        logger.info("✅ Redis dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install Redis dependencies: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error installing dependencies: {e}")
        return False


async def test_redis_connection():
    """Test Redis connection."""
    try:
        import aioredis
        
        logger.info("Testing Redis connection...")
        
        # Try to connect to Redis
        redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        
        # Test ping
        await redis.ping()
        
        # Test basic operations
        await redis.set("test_key", "test_value", ex=10)
        value = await redis.get("test_key")
        
        if value == "test_value":
            logger.info("✅ Redis connection test successful")
            await redis.delete("test_key")
            await redis.close()
            return True
        else:
            logger.error("❌ Redis test failed: unexpected value")
            await redis.close()
            return False
            
    except ImportError:
        logger.error("❌ Redis dependencies not installed")
        return False
    except Exception as e:
        logger.error(f"❌ Redis connection test failed: {e}")
        return False


def check_redis_server():
    """Check if Redis server is running."""
    try:
        import redis
        
        # Try to connect to Redis server
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        
        logger.info("✅ Redis server is running")
        return True
        
    except ImportError:
        logger.warning("⚠️  Redis package not installed")
        return False
    except Exception as e:
        logger.warning(f"⚠️  Redis server not accessible: {e}")
        return False


def print_redis_installation_guide():
    """Print Redis installation guide."""
    print("""
🔧 Redis Installation Guide:

Windows:
1. Download Redis from: https://github.com/microsoftarchive/redis/releases
2. Extract and run redis-server.exe
3. Or use Docker: docker run -d -p 6379:6379 redis:latest

Linux/macOS:
1. Ubuntu/Debian: sudo apt-get install redis-server
2. CentOS/RHEL: sudo yum install redis
3. macOS: brew install redis
4. Or use Docker: docker run -d -p 6379:6379 redis:latest

Docker (Recommended):
docker run -d --name redis-openmanus -p 6379:6379 redis:latest

After installation, start Redis server and run this script again.
""")


async def main():
    """Main setup function."""
    print("🚀 Setting up Redis for OpenManus...")
    
    # Step 1: Install Python dependencies
    deps_installed = await install_redis_dependencies()
    if not deps_installed:
        print("❌ Failed to install Redis dependencies")
        return False
    
    # Step 2: Check if Redis server is running
    redis_running = check_redis_server()
    if not redis_running:
        print("⚠️  Redis server is not running")
        print_redis_installation_guide()
        
        # Ask user if they want to continue anyway
        response = input("\nDo you want to continue setup anyway? (y/n): ").lower().strip()
        if response not in ['y', 'yes']:
            print("Setup cancelled. Please install and start Redis server first.")
            return False
    
    # Step 3: Test Redis connection (if server is running)
    if redis_running:
        connection_ok = await test_redis_connection()
        if not connection_ok:
            print("❌ Redis connection test failed")
            return False
    
    print("""
✅ Redis setup completed!

Next steps:
1. Make sure Redis server is running
2. Restart the OpenManus backend: python scripts/start_backend.py
3. Events will now be stored in Redis for better performance

Configuration:
- Redis URL: redis://localhost:6379/0
- Event expiry: 30 days
- Automatic fallback to SQLite if Redis is unavailable
""")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
