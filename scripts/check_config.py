#!/usr/bin/env python3
"""Check system configuration."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Check configuration."""
    print("🔧 Checking OpenManus Configuration...")
    
    try:
        # Import settings
        from app.settings import settings
        
        print("\n✅ Settings loaded successfully!")
        settings.print_config()
        
        # Test database connection
        print("\n🗄️  Testing database connection...")
        try:
            import asyncio
            from app.database.database import init_database, close_database
            
            async def test_db():
                try:
                    await init_database()
                    print("✅ Database connection successful!")
                    await close_database()
                    return True
                except Exception as e:
                    print(f"❌ Database connection failed: {e}")
                    return False
            
            success = asyncio.run(test_db())
            if not success:
                return False
                
        except Exception as e:
            print(f"❌ Database test failed: {e}")
            return False
        
        # Test event system
        print("\n📡 Testing event system...")
        try:
            from app.event.manager import event_manager
            print("✅ Event system loaded successfully!")
        except Exception as e:
            print(f"❌ Event system failed: {e}")
            return False
        
        # Test API imports
        print("\n🌐 Testing API imports...")
        try:
            from app.api.main import app
            print("✅ API application loaded successfully!")
        except Exception as e:
            print(f"❌ API import failed: {e}")
            return False
        
        print("\n🎉 All configuration checks passed!")
        print("\nNext steps:")
        print("1. Start the backend: python scripts/start_system.py --backend-only")
        print("2. Test the API: python scripts/test_api.py")
        print("3. Install frontend dependencies: cd frontend && npm install")
        print("4. Start frontend: cd frontend && npm run dev")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
