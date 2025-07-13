#!/usr/bin/env python3
"""Database reset script for OpenManus project."""

import asyncio
import argparse
import sys
import os
import sqlite3
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import logger
from app.settings import settings


def force_close_sqlite_connections(db_path: str):
    """Force close all SQLite connections to the database."""
    try:
        # Try to connect and immediately close to force unlock
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.execute("BEGIN IMMEDIATE;")
        conn.rollback()
        conn.close()
        logger.info(f"Forced close connections to {db_path}")
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.warning(f"Database {db_path} is locked, will attempt to delete anyway")
        else:
            logger.error(f"Error closing connections: {e}")
    except Exception as e:
        logger.error(f"Unexpected error closing connections: {e}")


def delete_database_file(db_path: str) -> bool:
    """Delete the database file if it exists."""
    try:
        db_file = Path(db_path)
        
        if not db_file.exists():
            logger.info(f"Database file {db_path} does not exist")
            return True
        
        # Force close connections first
        force_close_sqlite_connections(db_path)
        
        # Delete the main database file
        db_file.unlink()
        logger.info(f"Deleted database file: {db_path}")
        
        # Delete WAL and SHM files if they exist (SQLite journal files)
        wal_file = Path(f"{db_path}-wal")
        shm_file = Path(f"{db_path}-shm")
        
        if wal_file.exists():
            wal_file.unlink()
            logger.info(f"Deleted WAL file: {db_path}-wal")
        
        if shm_file.exists():
            shm_file.unlink()
            logger.info(f"Deleted SHM file: {db_path}-shm")
        
        return True
        
    except PermissionError:
        logger.error(f"Permission denied: Cannot delete {db_path}")
        logger.error("Make sure no other processes are using the database")
        return False
    except Exception as e:
        logger.error(f"Failed to delete database file {db_path}: {e}")
        return False


def extract_db_path_from_url(database_url: str) -> str:
    """Extract the database file path from the database URL."""
    if database_url.startswith("sqlite"):
        # Handle both sqlite:/// and sqlite+aiosqlite:/// formats
        if ":///" in database_url:
            path_part = database_url.split("///", 1)[1]
            # Remove query parameters if any
            if "?" in path_part:
                path_part = path_part.split("?")[0]
            return path_part
        else:
            raise ValueError(f"Invalid SQLite URL format: {database_url}")
    else:
        raise ValueError(f"Only SQLite databases are supported for file deletion. Got: {database_url}")


async def recreate_database():
    """Recreate the database with fresh tables."""
    try:
        from app.database.init import full_setup
        
        logger.info("Recreating database with fresh tables...")
        success = await full_setup(create_test=True)
        
        if success:
            logger.info("Database recreated successfully!")
            return True
        else:
            logger.error("Failed to recreate database")
            return False
            
    except Exception as e:
        logger.error(f"Error recreating database: {e}")
        return False


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Reset OpenManus Database")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deletion without confirmation"
    )
    parser.add_argument(
        "--no-recreate",
        action="store_true",
        help="Only delete, don't recreate the database"
    )
    parser.add_argument(
        "--with-test-data",
        action="store_true",
        help="Include test data when recreating"
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("🗄️  OpenManus Database Reset Tool")
        logger.info(f"Database URL: {settings.DATABASE_URL}")
        
        # Check if it's SQLite
        if not settings.DATABASE_URL.startswith("sqlite"):
            logger.error("This script only supports SQLite databases")
            logger.error("For other databases, use your database management tools")
            return False
        
        # Extract database file path
        try:
            db_path = extract_db_path_from_url(settings.DATABASE_URL)
            logger.info(f"Database file path: {db_path}")
        except ValueError as e:
            logger.error(str(e))
            return False
        
        # Confirmation
        if not args.force:
            print(f"\n⚠️  WARNING: This will permanently delete the database file:")
            print(f"   {db_path}")
            print(f"   All data will be lost!")
            
            response = input("\nAre you sure you want to continue? (yes/no): ").lower().strip()
            if response not in ["yes", "y"]:
                logger.info("Operation cancelled by user")
                return True
        
        # Step 1: Delete the database file
        logger.info("🗑️  Deleting database file...")
        if not delete_database_file(db_path):
            return False
        
        logger.info("✅ Database file deleted successfully")
        
        # Step 2: Recreate database (unless --no-recreate is specified)
        if not args.no_recreate:
            logger.info("🔄 Recreating database...")
            
            # Import here to avoid issues with deleted database
            success = await recreate_database()
            
            if success:
                logger.info("✅ Database recreated successfully!")
                
                if args.with_test_data:
                    logger.info("📝 Test data has been included")
                else:
                    logger.info("💡 To add test data, run: python scripts/db_manager.py setup --with-test-data")
                
            else:
                logger.error("❌ Failed to recreate database")
                return False
        else:
            logger.info("⏭️  Skipping database recreation (--no-recreate specified)")
        
        logger.info("🎉 Database reset completed successfully!")
        
        # Show next steps
        print("\n📋 Next steps:")
        if args.no_recreate:
            print("1. Run: python scripts/db_manager.py setup --with-test-data")
        print("2. Run: python scripts/check_config.py")
        print("3. Start the system: python scripts/start_system.py --backend-only")
        
        return True
        
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
