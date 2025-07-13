#!/usr/bin/env python3
"""
测试脚本：查看指定事件ID的完整事件链

用法:
    python scripts/test_event_chain.py c413c3ff-9a0a-4f1d-9615-4ceda5bd490d
    python scripts/test_event_chain.py --event-id c413c3ff-9a0a-4f1d-9615-4ceda5bd490d --format json
    python scripts/test_event_chain.py --event-id c413c3ff-9a0a-4f1d-9615-4ceda5bd490d --include-related
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logger import logger
from app.database.database import init_database, close_database
from app.database.tracker import EventTracker
from app.database.persistence import EventPersistence
from app.event.manager import event_manager


class EventChainAnalyzer:
    """事件链分析器"""

    def __init__(self):
        self.tracker = EventTracker()
        self.persistence = EventPersistence()

    async def analyze_event_chain(self, event_id: str, include_related: bool = False) -> Dict[str, Any]:
        """分析事件链

        Args:
            event_id: 事件ID
            include_related: 是否包含相关事件

        Returns:
            Dict[str, Any]: 分析结果
        """
        try:
            # 获取原始事件
            original_event = await self.persistence.get_event(event_id)
            if not original_event:
                return {
                    "error": f"Event {event_id} not found",
                    "event_id": event_id,
                    "found": False
                }

            # 获取事件链（基于root_event_id）
            event_chain = await self.tracker.get_event_chain(event_id)

            # 获取整个对话的所有事件
            conversation_events = []
            conversation_id = getattr(original_event, 'conversation_id', None)
            if conversation_id:
                conversation_events = await self.persistence.get_conversation_events(conversation_id)

            # 获取相关事件（如果需要）
            related_events = []
            if include_related:
                related_events = await self.tracker.get_related_events(event_id)

            # 构建分析结果
            result = {
                "event_id": event_id,
                "found": True,
                "original_event": self._format_event(original_event),
                "chain_analysis": {
                    "total_events": len(event_chain),
                    "root_event_id": getattr(original_event, 'root_event_id', event_id),
                    "chain_events": [self._format_event(evt) for evt in event_chain]
                },
                "conversation_analysis": {
                    "conversation_id": conversation_id,
                    "total_conversation_events": len(conversation_events),
                    "conversation_events": [self._format_event(evt) for evt in conversation_events]
                } if conversation_id else None,
                "related_events": {
                    "total_related": len(related_events),
                    "events": [self._format_event(evt) for evt in related_events]
                } if include_related else None,
                "analysis_timestamp": datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"Error analyzing event chain for {event_id}: {e}")
            return {
                "error": str(e),
                "event_id": event_id,
                "found": False
            }

    def _format_event(self, event) -> Dict[str, Any]:
        """格式化事件数据"""
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
            "source": getattr(event, 'source', None),
            "conversation_id": getattr(event, 'conversation_id', None),
            "user_id": getattr(event, 'user_id', None),
            "session_id": getattr(event, 'session_id', None),
            "parent_events": getattr(event, 'parent_events', []),
            "root_event_id": getattr(event, 'root_event_id', None),
            "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
            "priority": event.priority.value if hasattr(event.priority, 'value') else str(event.priority),
            "data": event.data,
            "metadata": getattr(event, 'metadata', {}),
            "processed_by": getattr(event, 'processed_by', []),
            "error_message": getattr(event, 'error_message', None)
        }

    def print_chain_summary(self, result: Dict[str, Any]):
        """打印事件链摘要"""
        if not result.get("found"):
            print(f"❌ Event not found: {result.get('error', 'Unknown error')}")
            return

        print(f"\n🔍 Event Chain Analysis for: {result['event_id']}")
        print("=" * 80)

        # 原始事件信息
        original = result["original_event"]
        print(f"\n📋 Original Event:")
        print(f"   ID: {original['event_id']}")
        print(f"   Type: {original['event_type']}")
        print(f"   Timestamp: {original['timestamp']}")
        print(f"   Source: {original['source']}")
        print(f"   Conversation: {original['conversation_id']}")
        print(f"   Status: {original['status']}")
        print(f"   Root Event: {original['root_event_id']}")

        # 事件链分析
        chain = result["chain_analysis"]
        print(f"\n🔗 Event Chain Analysis (Root-based):")
        print(f"   Total Events in Chain: {chain['total_events']}")
        print(f"   Root Event ID: {chain['root_event_id']}")

        if chain["chain_events"]:
            print(f"\n📊 Chain Events (chronological order):")
            for i, event in enumerate(chain["chain_events"], 1):
                print(f"   {i}. [{event['timestamp']}] {event['event_type']}")
                print(f"      ID: {event['event_id']}")
                print(f"      Source: {event['source']}")
                print(f"      Status: {event['status']}")
                if event['parent_events']:
                    print(f"      Parents: {event['parent_events']}")
                if event.get('data'):
                    # 简化显示数据
                    data_summary = str(event['data'])[:100] + "..." if len(str(event['data'])) > 100 else str(event['data'])
                    print(f"      Data: {data_summary}")
                print()

        # 对话事件分析
        if result.get("conversation_analysis"):
            conv = result["conversation_analysis"]
            print(f"\n💬 Conversation Events Analysis:")
            print(f"   Conversation ID: {conv['conversation_id']}")
            print(f"   Total Events in Conversation: {conv['total_conversation_events']}")

            if conv["conversation_events"]:
                print(f"\n📋 All Conversation Events (chronological order):")
                for i, event in enumerate(conv["conversation_events"], 1):
                    # 标记目标事件
                    marker = "👉 " if event['event_id'] == result['event_id'] else "   "
                    print(f"{marker}{i:2d}. [{event['timestamp']}] {event['event_type']}")
                    print(f"      ID: {event['event_id']}")
                    print(f"      Source: {event['source']}")
                    print(f"      Status: {event['status']}")
                    if event['parent_events']:
                        print(f"      Parents: {event['parent_events']}")
                    if event.get('data'):
                        # 简化显示数据
                        data_summary = str(event['data']) if len(str(event['data'])) > 100 else str(event['data'])
                        print(f"      Data: {data_summary}")
                    print()

        # 相关事件
        if result.get("related_events"):
            related = result["related_events"]
            print(f"🔄 Related Events: {related['total_related']}")
            if related["events"]:
                for event in related["events"]:
                    print(f"   - {event['event_type']} ({event['event_id'][:8]}...)")

        print("=" * 80)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="分析事件链")
    parser.add_argument("event_id", nargs="?", help="事件ID")
    parser.add_argument("--event-id", help="事件ID (替代位置参数)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    parser.add_argument("--include-related", action="store_true", help="包含相关事件")
    parser.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    # 获取事件ID
    event_id = args.event_id or args.event_id
    if not event_id:
        print("❌ 请提供事件ID")
        print("用法: python scripts/test_event_chain.py <event_id>")
        sys.exit(1)

    try:
        # 初始化数据库
        await init_database()

        # 初始化事件管理器
        await event_manager.initialize()

        # 创建分析器
        analyzer = EventChainAnalyzer()

        # 分析事件链
        print(f"🔍 Analyzing event chain for: {event_id}")
        result = await analyzer.analyze_event_chain(event_id, args.include_related)

        # 输出结果
        if args.format == "json":
            output_data = json.dumps(result, indent=2, ensure_ascii=False)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_data)
                print(f"✅ Results saved to: {args.output}")
            else:
                print(output_data)
        else:
            analyzer.print_chain_summary(result)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    # 重定向输出到文件
                    import io
                    from contextlib import redirect_stdout

                    string_buffer = io.StringIO()
                    with redirect_stdout(string_buffer):
                        analyzer.print_chain_summary(result)
                    f.write(string_buffer.getvalue())
                print(f"✅ Results saved to: {args.output}")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

    finally:
        # 清理资源
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
