#!/usr/bin/env python3
"""Initialize database for OpenManus project."""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import logger
from app.database.init import full_setup, cleanup


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Initialize OpenManus Database")
    parser.add_argument(
        "--with-test-data",
        action="store_true",
        help="Include test data"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force initialization even if database exists"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("🗄️  Initializing OpenManus Database...")
        
        if not args.force:
            # Check if database already exists and has data
            try:
                from app.database.database import get_database
                from app.database.models import User
                from sqlalchemy import select, func
                
                async for session in get_database():
                    result = await session.execute(select(func.count(User.id)))
                    user_count = result.scalar()
                    
                    if user_count > 0:
                        print(f"\n⚠️  Database already contains {user_count} users.")
                        response = input("Do you want to continue anyway? (yes/no): ").lower().strip()
                        if response not in ["yes", "y"]:
                            logger.info("Initialization cancelled by user")
                            return True
                    break
                    
            except Exception:
                # Database doesn't exist or has issues, proceed with initialization
                pass
        
        # Initialize database
        success = await full_setup(create_test=args.with_test_data)
        
        if success:
            logger.info("✅ Database initialization completed successfully!")
            
            if args.with_test_data:
                print("\n📝 Test data created:")
                print("  - Username: testuser")
                print("  - Email: test@example.com") 
                print("  - Password: testpassword")
            
            print("\n🚀 Next steps:")
            print("1. Start the backend: python scripts/start_system.py --backend-only --skip-setup")
            print("2. Test the API: python scripts/debug_api.py")
            print("3. Visit API docs: http://localhost:8000/docs")
            
            return True
        else:
            logger.error("❌ Database initialization failed")
            return False
            
    except KeyboardInterrupt:
        logger.info("Initialization interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return False
    finally:
        await cleanup()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
