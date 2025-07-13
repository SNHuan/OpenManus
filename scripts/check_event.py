#!/usr/bin/env python3
"""
简单事件检查脚本 - 直接查询数据库

用法:
    python scripts/check_event.py c413c3ff-9a0a-4f1d-9615-4ceda5bd490d
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime


def check_event_in_db(event_id: str, db_path: str = "openmanus.db"):
    """直接在SQLite数据库中查询事件"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
        cursor = conn.cursor()
        
        print(f"🔍 Checking event: {event_id}")
        print(f"📁 Database: {db_path}")
        print("=" * 80)
        
        # 查询目标事件
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        target_event = cursor.fetchone()
        
        if not target_event:
            print(f"❌ Event {event_id} not found in database")
            
            # 检查是否有类似的事件ID
            cursor.execute("SELECT id FROM events WHERE id LIKE ?", (f"%{event_id[-8:]}%",))
            similar_events = cursor.fetchall()
            
            if similar_events:
                print(f"\n🔍 Found {len(similar_events)} events with similar ID suffix:")
                for event in similar_events[:10]:  # 只显示前10个
                    print(f"   - {event['id']}")
            
            return
        
        print(f"✅ Event found!")
        print(f"\n📋 Event Details:")
        print(f"   ID: {target_event['id']}")
        print(f"   Type: {target_event['event_type']}")
        print(f"   Timestamp: {target_event['timestamp']}")
        print(f"   Source: {target_event['source']}")
        print(f"   Conversation ID: {target_event['conversation_id']}")
        print(f"   User ID: {target_event['user_id']}")
        print(f"   Session ID: {target_event['session_id']}")
        print(f"   Root Event ID: {target_event['root_event_id']}")
        print(f"   Status: {target_event['status']}")
        
        # 解析JSON字段
        if target_event['parent_events']:
            try:
                parent_events = json.loads(target_event['parent_events'])
                print(f"   Parent Events: {parent_events}")
            except:
                print(f"   Parent Events: {target_event['parent_events']}")
        
        if target_event['data']:
            try:
                data = json.loads(target_event['data'])
                print(f"   Data: {json.dumps(data, indent=6, ensure_ascii=False)}")
            except:
                print(f"   Data: {target_event['data']}")
        
        if target_event['metadata']:
            try:
                metadata = json.loads(target_event['metadata'])
                print(f"   Metadata: {json.dumps(metadata, indent=6, ensure_ascii=False)}")
            except:
                print(f"   Metadata: {target_event['metadata']}")
        
        if target_event['processed_by']:
            try:
                processed_by = json.loads(target_event['processed_by'])
                print(f"   Processed By: {processed_by}")
            except:
                print(f"   Processed By: {target_event['processed_by']}")
        
        if target_event['error_message']:
            print(f"   ❌ Error: {target_event['error_message']}")
        
        # 查询事件链
        root_event_id = target_event['root_event_id'] or event_id
        
        print(f"\n🔗 Event Chain (Root: {root_event_id}):")
        print("-" * 80)
        
        cursor.execute("""
            SELECT * FROM events 
            WHERE root_event_id = ? OR id = ?
            ORDER BY timestamp
        """, (root_event_id, root_event_id))
        
        chain_events = cursor.fetchall()
        
        for i, event in enumerate(chain_events, 1):
            marker = "👉 " if event['id'] == event_id else "   "
            print(f"{marker}{i:2d}. [{event['timestamp']}] {event['event_type']}")
            print(f"      ID: {event['id']}")
            print(f"      Source: {event['source'] or 'Unknown'}")
            print(f"      Status: {event['status']}")
            
            if event['data']:
                try:
                    data = json.loads(event['data'])
                    # 简化显示
                    if 'content' in data:
                        content = str(data['content'])[:100] + "..." if len(str(data['content'])) > 100 else str(data['content'])
                        print(f"      Content: {content}")
                    if 'tool_name' in data:
                        print(f"      Tool: {data['tool_name']}")
                    if 'step_number' in data:
                        print(f"      Step: {data['step_number']}")
                except:
                    data_str = str(event['data'])[:100] + "..." if len(str(event['data'])) > 100 else str(event['data'])
                    print(f"      Data: {data_str}")
            
            print()
        
        # 统计信息
        print("📊 Chain Statistics:")
        print(f"   Total Events: {len(chain_events)}")
        
        event_types = {}
        for event in chain_events:
            event_types[event['event_type']] = event_types.get(event['event_type'], 0) + 1
        
        print(f"   Event Types: {dict(event_types)}")
        
        # 查询相关对话信息
        if target_event['conversation_id']:
            print(f"\n💬 Conversation Info:")
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (target_event['conversation_id'],))
            conversation = cursor.fetchone()
            
            if conversation:
                print(f"   Conversation ID: {conversation['id']}")
                print(f"   Title: {conversation['title']}")
                print(f"   Status: {conversation['status']}")
                print(f"   User ID: {conversation['user_id']}")
                print(f"   Created: {conversation['created_at']}")
                print(f"   Updated: {conversation['updated_at']}")
        
        # 查询用户信息
        if target_event['user_id']:
            print(f"\n👤 User Info:")
            cursor.execute("SELECT username, email, created_at FROM users WHERE id = ?", (target_event['user_id'],))
            user = cursor.fetchone()
            
            if user:
                print(f"   User ID: {target_event['user_id']}")
                print(f"   Username: {user['username']}")
                print(f"   Email: {user['email']}")
                print(f"   Created: {user['created_at']}")
        
        print("=" * 80)
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("❌ Usage: python scripts/check_event.py <event_id>")
        print("Example: python scripts/check_event.py c413c3ff-9a0a-4f1d-9615-4ceda5bd490d")
        sys.exit(1)
    
    event_id = sys.argv[1]
    
    # 检查数据库文件是否存在
    db_path = "openmanus.db"
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        print("Please make sure you're running this script from the project root directory.")
        sys.exit(1)
    
    check_event_in_db(event_id, db_path)


if __name__ == "__main__":
    main()
