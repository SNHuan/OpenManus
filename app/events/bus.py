"""
事件总线实现
提供事件的发布、订阅和分发功能
"""

import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any
from collections import defaultdict
from .types import Event, EventType


class EventBus:
    """事件总线 - 系统的核心事件路由器"""

    def __init__(self):
        # 事件类型订阅者：event_type -> [handlers]
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)

        # 组件订阅者：component_name -> [handlers]
        self.component_subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # 通配符订阅者：订阅所有事件
        self.wildcard_subscribers: List[Callable] = []

        # 事件队列
        self.event_queue: asyncio.Queue = asyncio.Queue()

        # 运行状态
        self.running = False
        self.processor_task: Optional[asyncio.Task] = None

        # 日志记录器
        self.logger = logging.getLogger(__name__)

        # 统计信息
        self.stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "subscribers_count": 0
        }

    async def start(self):
        """启动事件总线"""
        if self.running:
            self.logger.warning("EventBus is already running")
            return

        self.running = True
        self.processor_task = asyncio.create_task(self._process_events())
        self.logger.info("EventBus started")

    async def stop(self):
        """停止事件总线"""
        if not self.running:
            return

        self.running = False

        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("EventBus stopped")

    async def publish(self, event: Event):
        """发布事件到队列"""
        if not self.running:
            self.logger.warning("EventBus is not running, event will be queued")

        await self.event_queue.put(event)
        self.stats["events_published"] += 1
        self.logger.debug(f"Event published: {event.event_type} from {event.source}")

    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅特定类型的事件"""
        self.subscribers[event_type].append(handler)
        self.stats["subscribers_count"] += 1
        self.logger.debug(f"Handler subscribed to {event_type}")

    def subscribe_component(self, component_name: str, handler: Callable):
        """订阅来自特定组件的所有事件"""
        self.component_subscribers[component_name].append(handler)
        self.stats["subscribers_count"] += 1
        self.logger.debug(f"Handler subscribed to component {component_name}")

    def subscribe_all(self, handler: Callable):
        """订阅所有事件（通配符订阅）"""
        self.wildcard_subscribers.append(handler)
        self.stats["subscribers_count"] += 1
        self.logger.debug("Handler subscribed to all events")

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """取消订阅特定事件类型"""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            self.stats["subscribers_count"] -= 1
            self.logger.debug(f"Handler unsubscribed from {event_type}")

    def unsubscribe_component(self, component_name: str, handler: Callable):
        """取消订阅特定组件"""
        if handler in self.component_subscribers[component_name]:
            self.component_subscribers[component_name].remove(handler)
            self.stats["subscribers_count"] -= 1
            self.logger.debug(f"Handler unsubscribed from component {component_name}")

    async def _process_events(self):
        """事件处理循环"""
        self.logger.info("Event processing loop started")

        while self.running:
            try:
                # 等待事件，设置超时避免无限等待
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # 处理事件
                await self._handle_event(event)
                self.stats["events_processed"] += 1

            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                self.stats["events_failed"] += 1

    async def _handle_event(self, event: Event):
        """处理单个事件"""
        handlers_set = set()

        # 收集所有相关的处理器（使用set去重）

        # 1. 事件类型订阅者
        handlers_set.update(self.subscribers.get(event.event_type, []))

        # 2. 组件订阅者（来源组件）
        handlers_set.update(self.component_subscribers.get(event.source, []))

        # 3. 通配符订阅者
        handlers_set.update(self.wildcard_subscribers)

        # 4. 如果有目标组件，添加目标组件的订阅者
        if event.target:
            target_handlers = self.component_subscribers.get(event.target, [])
            handlers_set.update(target_handlers)

        # 转换为列表
        handlers = list(handlers_set)

        # 并发执行所有处理器
        if handlers:
            tasks = [self._safe_call_handler(handler, event) for handler in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否有处理器执行失败
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Handler {i} failed for event {event.event_type}: {result}")

        self.logger.debug(f"Event {event.event_type} handled by {len(handlers)} handlers")

    async def _safe_call_handler(self, handler: Callable, event: Event):
        """安全调用事件处理器"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # 对于同步函数，在线程池中执行以避免阻塞
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)
        except Exception as e:
            self.logger.error(f"Error in event handler: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        return {
            **self.stats,
            "queue_size": self.event_queue.qsize(),
            "is_running": self.running,
            "event_type_subscribers": {
                event_type.value: len(handlers)
                for event_type, handlers in self.subscribers.items()
            },
            "component_subscribers": {
                component: len(handlers)
                for component, handlers in self.component_subscribers.items()
            },
            "wildcard_subscribers": len(self.wildcard_subscribers)
        }

    async def wait_for_event(self, event_type: EventType, timeout: float = 30.0) -> Optional[Event]:
        """等待特定类型的事件（用于测试和调试）"""
        future = asyncio.Future()

        def handler(event: Event):
            if not future.done():
                future.set_result(event)

        # 临时订阅
        self.subscribe(event_type, handler)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return None
        finally:
            # 清理订阅
            self.unsubscribe(event_type, handler)


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


async def init_event_bus():
    """初始化全局事件总线"""
    event_bus = get_event_bus()
    if not event_bus.running:
        await event_bus.start()


async def shutdown_event_bus():
    """关闭全局事件总线"""
    global _global_event_bus
    if _global_event_bus and _global_event_bus.running:
        await _global_event_bus.stop()
        _global_event_bus = None
