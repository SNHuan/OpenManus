#!/usr/bin/env python3
"""
快速事件追踪脚本 - 查看指定事件ID的事件链

用法:
    python scripts/quick_event_trace.py c413c3ff-9a0a-4f1d-9615-4ceda5bd490d
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logger import logger
from app.database.database import init_database, close_database, get_database
from app.database.models import Event as EventModel
from sqlalchemy import select, or_, text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_event_chain_direct(event_id: str) -> list:
    """直接从数据库获取事件链"""
    async for session in get_database():
        try:
            # 首先获取目标事件
            stmt = select(EventModel).where(EventModel.id == event_id)
            result = await session.execute(stmt)
            target_event = result.scalar_one_or_none()
            
            if not target_event:
                print(f"❌ Event {event_id} not found in database")
                return []
            
            # 获取根事件ID
            root_event_id = target_event.root_event_id or event_id
            
            # 获取整个事件链
            stmt = select(EventModel).where(
                or_(
                    EventModel.root_event_id == root_event_id,
                    EventModel.id == root_event_id
                )
            ).order_by(EventModel.timestamp)
            
            result = await session.execute(stmt)
            events = result.scalars().all()
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting event chain: {e}")
            return []


def format_event_data(data):
    """格式化事件数据用于显示"""
    if not data:
        return "None"
    
    if isinstance(data, dict):
        # 提取关键信息
        key_info = []
        if 'content' in data:
            content = str(data['content'])[:100] + "..." if len(str(data['content'])) > 100 else str(data['content'])
            key_info.append(f"content: {content}")
        if 'tool_name' in data:
            key_info.append(f"tool: {data['tool_name']}")
        if 'step_number' in data:
            key_info.append(f"step: {data['step_number']}")
        if 'status' in data:
            key_info.append(f"status: {data['status']}")
        
        return " | ".join(key_info) if key_info else str(data)[:100]
    
    return str(data)[:100]


def print_event_chain(events: list, target_event_id: str):
    """打印事件链"""
    if not events:
        print("❌ No events found")
        return
    
    print(f"\n🔍 Event Chain Analysis for: {target_event_id}")
    print("=" * 100)
    
    # 找到目标事件
    target_event = None
    for event in events:
        if event.id == target_event_id:
            target_event = event
            break
    
    if target_event:
        print(f"\n📋 Target Event Info:")
        print(f"   ID: {target_event.id}")
        print(f"   Type: {target_event.event_type}")
        print(f"   Timestamp: {target_event.timestamp}")
        print(f"   Source: {target_event.source}")
        print(f"   Conversation: {target_event.conversation_id}")
        print(f"   Root Event: {target_event.root_event_id}")
        print(f"   Status: {target_event.status}")
        if target_event.parent_events:
            print(f"   Parent Events: {target_event.parent_events}")
    
    print(f"\n🔗 Complete Event Chain ({len(events)} events):")
    print("-" * 100)
    
    for i, event in enumerate(events, 1):
        # 标记目标事件
        marker = "👉 " if event.id == target_event_id else "   "
        
        print(f"{marker}{i:2d}. [{event.timestamp}] {event.event_type}")
        print(f"      ID: {event.id}")
        print(f"      Source: {event.source or 'Unknown'}")
        print(f"      Status: {event.status}")
        
        if event.parent_events:
            print(f"      Parents: {event.parent_events}")
        
        if event.data:
            data_summary = format_event_data(event.data)
            print(f"      Data: {data_summary}")
        
        if event.error_message:
            print(f"      ❌ Error: {event.error_message}")
        
        print()
    
    print("=" * 100)
    
    # 统计信息
    event_types = {}
    sources = {}
    statuses = {}
    
    for event in events:
        event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        sources[event.source or 'Unknown'] = sources.get(event.source or 'Unknown', 0) + 1
        statuses[event.status] = statuses.get(event.status, 0) + 1
    
    print(f"\n📊 Chain Statistics:")
    print(f"   Total Events: {len(events)}")
    print(f"   Event Types: {dict(event_types)}")
    print(f"   Sources: {dict(sources)}")
    print(f"   Statuses: {dict(statuses)}")
    
    # 时间跨度
    if len(events) > 1:
        start_time = events[0].timestamp
        end_time = events[-1].timestamp
        duration = end_time - start_time
        print(f"   Time Span: {duration}")
        print(f"   Start: {start_time}")
        print(f"   End: {end_time}")


async def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("❌ Usage: python scripts/quick_event_trace.py <event_id>")
        print("Example: python scripts/quick_event_trace.py c413c3ff-9a0a-4f1d-9615-4ceda5bd490d")
        sys.exit(1)
    
    event_id = sys.argv[1]
    
    try:
        print(f"🚀 Starting event chain analysis...")
        print(f"📋 Target Event ID: {event_id}")
        
        # 初始化数据库
        await init_database()
        
        # 获取事件链
        events = await get_event_chain_direct(event_id)
        
        # 打印结果
        print_event_chain(events, event_id)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # 清理资源
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
