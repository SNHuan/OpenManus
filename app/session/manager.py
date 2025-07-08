"""
会话管理器
负责会话的生命周期管理和状态维护
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

from app.events.bus import EventBus
from app.events.types import Event, EventType, SessionInfo, AgentExecutionRequest


class SessionManager:
    """会话管理器 - 管理会话的完整生命周期"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.component_name = "session_manager"
        self.sessions: Dict[str, SessionInfo] = {}
        self.logger = logging.getLogger(__name__)

        # 订阅相关事件
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """订阅会话相关事件"""
        self.event_bus.subscribe(EventType.SESSION_CREATE_REQUEST, self._on_create_session)
        self.event_bus.subscribe(EventType.SESSION_START_REQUEST, self._on_start_session)
        self.event_bus.subscribe(EventType.SESSION_STOP_REQUEST, self._on_stop_session)
        self.event_bus.subscribe(EventType.SESSION_STOPPED, self._on_session_stopped)

        self.logger.info("SessionManager subscribed to events")

    async def _on_create_session(self, event: Event):
        """处理会话创建请求"""
        self.logger.info(f"Processing session creation request: {event.event_id}")
        try:
            request_data = event.data
            self.logger.info(f"Request data: {request_data}")

            # 创建会话信息
            session = SessionInfo(
                agent_name=request_data.get("agent_type", "manus"),
                status="created",
                config=request_data.get("config", {})
            )

            # 保存会话
            self.sessions[session.session_id] = session

            self.logger.info(f"Session created: {session.session_id}")

            # 发布会话创建成功事件
            created_event = Event(
                event_type=EventType.SESSION_CREATED,
                source=self.component_name,
                session_id=session.session_id,
                correlation_id=event.event_id,
                data={
                    "session": session.model_dump(),
                    "original_request": request_data
                }
            )

            await self.event_bus.publish(created_event)
            self.logger.info(f"Published SESSION_CREATED event for {session.session_id}")

            # 自动发布启动请求
            start_event = Event(
                event_type=EventType.SESSION_START_REQUEST,
                source=self.component_name,
                session_id=session.session_id,
                correlation_id=event.event_id,
                data=request_data
            )

            await self.event_bus.publish(start_event)
            self.logger.info(f"Published SESSION_START_REQUEST event for {session.session_id}")

        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SESSION_ERROR,
                source=self.component_name,
                correlation_id=event.event_id,
                data={"error": str(e), "stage": "creation"}
            )
            await self.event_bus.publish(error_event)

    async def _on_start_session(self, event: Event):
        """处理会话启动请求"""
        session_id = event.session_id

        if session_id not in self.sessions:
            self.logger.error(f"Session not found: {session_id}")
            return

        # 检查事件是否已经是发给执行管理器的
        if event.target == "execution_manager":
            self.logger.info(f"Event already targeted to execution_manager, skipping")
            return

        try:
            # 更新会话状态
            session = self.sessions[session_id]
            session.status = "starting"
            session.updated_at = datetime.now()

            self.logger.info(f"Session starting: {session_id}")

            # 转发给执行管理器（如果事件还没有target）
            if not event.target:
                exec_event = Event(
                    event_type=EventType.SESSION_START_REQUEST,
                    source=self.component_name,
                    target="execution_manager",
                    session_id=session_id,
                    correlation_id=event.correlation_id,
                    data=event.data
                )

                await self.event_bus.publish(exec_event)
                self.logger.info(f"Forwarded SESSION_START_REQUEST to execution_manager for {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to start session {session_id}: {e}")
            await self._publish_session_error(session_id, str(e), "starting")

    async def _on_stop_session(self, event: Event):
        """处理会话停止请求"""
        session_id = event.session_id

        if session_id not in self.sessions:
            self.logger.error(f"Session not found: {session_id}")
            return

        try:
            # 检查会话状态，避免重复处理
            session = self.sessions[session_id]
            if session.status in ["stopping", "stopped"]:
                self.logger.info(f"Session {session_id} already in {session.status} state, ignoring stop request")
                return

            # 更新会话状态
            session.status = "stopping"
            session.updated_at = datetime.now()

            self.logger.info(f"Session stopping: {session_id}")

            # 转发给执行管理器（只有当事件还没有target时）
            if not event.target:
                stop_event = Event(
                    event_type=EventType.SESSION_STOP_REQUEST,
                    source=self.component_name,
                    target="execution_manager",
                    session_id=session_id,
                    data=event.data
                )

                await self.event_bus.publish(stop_event)

        except Exception as e:
            self.logger.error(f"Failed to stop session {session_id}: {e}")
            await self._publish_session_error(session_id, str(e), "stopping")

    async def _on_session_stopped(self, event: Event):
        """处理会话已停止事件"""
        session_id = event.session_id

        if session_id not in self.sessions:
            self.logger.warning(f"Received STOPPED event for unknown session: {session_id}")
            return

        try:
            # 更新会话状态为已停止
            session = self.sessions[session_id]
            session.status = "stopped"
            session.updated_at = datetime.now()

            # 可以添加结果信息
            if event.data and "result" in event.data:
                session.result = event.data["result"]

            self.logger.info(f"Session stopped: {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to handle session stopped event for {session_id}: {e}")

    async def _publish_session_error(self, session_id: str, error_message: str, stage: str):
        """发布会话错误事件"""
        # 更新会话状态
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.status = "error"
            session.error_message = error_message
            session.updated_at = datetime.now()

        error_event = Event(
            event_type=EventType.SESSION_ERROR,
            source=self.component_name,
            session_id=session_id,
            data={
                "error": error_message,
                "stage": stage
            }
        )
        await self.event_bus.publish(error_event)

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息"""
        return self.sessions.get(session_id)

    def list_sessions(self, status: Optional[str] = None) -> List[SessionInfo]:
        """列出会话"""
        sessions = list(self.sessions.values())

        if status:
            sessions = [s for s in sessions if s.status == status]

        # 按创建时间倒序排列
        sessions.sort(key=lambda x: x.created_at, reverse=True)

        return sessions

    def get_active_sessions(self) -> List[SessionInfo]:
        """获取活跃会话"""
        return [s for s in self.sessions.values() if s.status in ["running", "starting"]]

    async def update_session_status(self, session_id: str, status: str, **kwargs):
        """更新会话状态"""
        if session_id not in self.sessions:
            self.logger.warning(f"Attempting to update non-existent session: {session_id}")
            return

        session = self.sessions[session_id]
        old_status = session.status
        session.status = status
        session.updated_at = datetime.now()

        # 更新其他字段
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        self.logger.info(f"Session {session_id} status updated: {old_status} -> {status}")

        # 发布状态更新事件
        if status in ["completed", "error", "stopped"]:
            event_type = EventType.SESSION_STOPPED
        elif status == "running":
            event_type = EventType.SESSION_STARTED
        else:
            return  # 中间状态不发布事件

        status_event = Event(
            event_type=event_type,
            source=self.component_name,
            session_id=session_id,
            data={
                "session": session.model_dump(),
                "old_status": old_status,
                "new_status": status
            }
        )

        await self.event_bus.publish(status_event)

    def get_stats(self) -> Dict:
        """获取会话管理器统计信息"""
        status_counts = {}
        for session in self.sessions.values():
            status_counts[session.status] = status_counts.get(session.status, 0) + 1

        return {
            "total_sessions": len(self.sessions),
            "status_counts": status_counts,
            "active_sessions": len(self.get_active_sessions())
        }
