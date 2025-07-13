#!/usr/bin/env python3
"""Check database contents for debugging."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.database import get_database
from app.database.models import User, Conversation, Event
from sqlalchemy import select, func

async def check_users():
    """Check all users in database."""
    print("👥 Checking users in database...")
    
    try:
        async for session in get_database():
            # Count users
            count_result = await session.execute(select(func.count(User.id)))
            user_count = count_result.scalar()
            print(f"Total users: {user_count}")
            
            # Get all users
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            if users:
                print("\nUsers found:")
                for user in users:
                    print(f"  - ID: {user.id}")
                    print(f"    Username: {user.username}")
                    print(f"    Email: {user.email}")
                    print(f"    Created: {user.created_at}")
                    print(f"    Last login: {user.last_login}")
                    print()
            else:
                print("No users found in database")
            
            break
            
    except Exception as e:
        print(f"❌ Error checking users: {e}")

async def check_conversations():
    """Check all conversations in database."""
    print("💬 Checking conversations in database...")
    
    try:
        async for session in get_database():
            # Count conversations
            count_result = await session.execute(select(func.count(Conversation.id)))
            conv_count = count_result.scalar()
            print(f"Total conversations: {conv_count}")
            
            # Get all conversations
            result = await session.execute(select(Conversation))
            conversations = result.scalars().all()
            
            if conversations:
                print("\nConversations found:")
                for conv in conversations:
                    print(f"  - ID: {conv.id}")
                    print(f"    Title: {conv.title}")
                    print(f"    User ID: {conv.user_id}")
                    print(f"    Status: {conv.status}")
                    print(f"    Created: {conv.created_at}")
                    print()
            else:
                print("No conversations found in database")
            
            break
            
    except Exception as e:
        print(f"❌ Error checking conversations: {e}")

async def check_events():
    """Check events in database."""
    print("📡 Checking events in database...")
    
    try:
        async for session in get_database():
            # Count events
            count_result = await session.execute(select(func.count(Event.id)))
            event_count = count_result.scalar()
            print(f"Total events: {event_count}")
            
            # Get recent events
            result = await session.execute(
                select(Event).order_by(Event.timestamp.desc()).limit(5)
            )
            events = result.scalars().all()
            
            if events:
                print("\nRecent events:")
                for event in events:
                    print(f"  - ID: {event.id}")
                    print(f"    Type: {event.event_type}")
                    print(f"    Source: {event.source}")
                    print(f"    Timestamp: {event.timestamp}")
                    print(f"    Status: {event.status}")
                    print()
            else:
                print("No events found in database")
            
            break
            
    except Exception as e:
        print(f"❌ Error checking events: {e}")

async def test_user_lookup(username: str, email: str):
    """Test user lookup logic."""
    print(f"🔍 Testing user lookup for username='{username}', email='{email}'...")
    
    try:
        async for session in get_database():
            # Same query as in auth service
            stmt = select(User).where(
                (User.username == username) | (User.email == email)
            )
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"❌ User found:")
                print(f"  - Username: {existing_user.username}")
                print(f"  - Email: {existing_user.email}")
                print(f"  - ID: {existing_user.id}")
                
                if existing_user.username == username:
                    print(f"  - Conflict: Username '{username}' already exists")
                if existing_user.email == email:
                    print(f"  - Conflict: Email '{email}' already exists")
            else:
                print(f"✅ No user found with username '{username}' or email '{email}'")
            
            break
            
    except Exception as e:
        print(f"❌ Error testing user lookup: {e}")

async def main():
    """Main function."""
    print("🔍 Database Content Check")
    print("=" * 50)
    
    try:
        await check_users()
        print()
        await check_conversations()
        print()
        await check_events()
        print()
        
        # Test specific lookups
        await test_user_lookup("debuguser", "debug@example.com")
        print()
        await test_user_lookup("testuser", "test@example.com")
        
    except Exception as e:
        print(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
