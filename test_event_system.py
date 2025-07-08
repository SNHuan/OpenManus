#!/usr/bin/env python3
"""
测试事件系统
验证事件总线和组件通信是否正常工作
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置配置文件
os.environ["OPENMANUS_CONFIG"] = str(project_root / "config" / "config-doubao.toml")

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

try:
    from app.events.bus import EventBus
    from app.events.types import Event, EventType
    from app.session.manager import SessionManager
    from app.execution.manager import ExecutionManager
except ImportError as e:
    print(f"导入失败: {e}")
    sys.exit(1)


async def test_event_system():
    """测试事件系统"""
    print("🧪 测试事件系统...")
    
    # 创建事件总线
    event_bus = EventBus()
    await event_bus.start()
    
    # 创建管理器
    session_manager = SessionManager(event_bus)
    execution_manager = ExecutionManager(event_bus)
    
    print("✅ 组件创建成功")
    
    # 测试事件发布
    test_event = Event(
        event_type=EventType.SESSION_CREATE_REQUEST,
        source="test_client",
        data={
            "prompt": "测试任务",
            "agent_type": "manus",
            "config": {},
            "max_steps": 3
        }
    )
    
    print(f"📤 发布测试事件: {test_event.event_type}")
    await event_bus.publish(test_event)
    
    # 等待事件处理
    await asyncio.sleep(2)
    
    # 检查会话是否创建
    sessions = session_manager.list_sessions()
    print(f"📊 当前会话数量: {len(sessions)}")
    
    if sessions:
        session = sessions[0]
        print(f"✅ 会话创建成功: {session.session_id}")
        print(f"   状态: {session.status}")
        print(f"   Agent: {session.agent_name}")
        
        # 等待Agent执行
        print("⏳ 等待Agent执行...")
        await asyncio.sleep(10)
        
        # 检查执行状态
        running_sessions = execution_manager.get_running_sessions()
        print(f"🏃 运行中的会话: {running_sessions}")
        
        # 获取更新后的会话状态
        updated_session = session_manager.get_session(session.session_id)
        if updated_session:
            print(f"📈 会话状态更新: {updated_session.status}")
    else:
        print("❌ 没有创建会话")
    
    # 获取统计信息
    print("\n📊 系统统计:")
    print(f"   事件总线: {event_bus.get_stats()}")
    print(f"   会话管理器: {session_manager.get_stats()}")
    print(f"   执行管理器: {execution_manager.get_stats()}")
    
    # 清理
    await event_bus.stop()
    print("🧹 清理完成")


async def main():
    """主函数"""
    print("🚀 OpenManus 事件系统测试")
    print("=" * 50)
    
    try:
        await test_event_system()
        print("\n🎉 事件系统测试完成！")
    except Exception as e:
        print(f"\n💥 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
