"""
HTTP API服务器
提供RESTful API接口用于会话管理
"""

import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.events.bus import EventBus, get_event_bus, init_event_bus, shutdown_event_bus
from app.events.types import Event, EventType, AgentExecutionRequest, ContinueRequest, SessionInfo
from app.session.manager import SessionManager
from app.execution.manager import ExecutionManager
from app.sandbox.core.manager import SandboxManager
from app.sandbox.event_manager import SandboxEventManager


# 全局组件实例
session_manager: Optional[SessionManager] = None
execution_manager: Optional[ExecutionManager] = None
sandbox_manager: Optional[SandboxManager] = None
sandbox_event_manager: Optional[SandboxEventManager] = None
event_bus: Optional[EventBus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global session_manager, execution_manager, sandbox_manager, sandbox_event_manager, event_bus

    # 启动时初始化
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # 初始化事件总线
        await init_event_bus()
        event_bus = get_event_bus()

        # 初始化管理器
        session_manager = SessionManager(event_bus)
        execution_manager = ExecutionManager(event_bus)

        # 初始化沙箱管理器
        sandbox_manager = SandboxManager()
        sandbox_event_manager = SandboxEventManager(event_bus, sandbox_manager)

        # 注册事件广播处理器
        event_bus.subscribe_all(broadcast_event_handler)
        logger.info("Event broadcast handler registered")

        logger.info("OpenManus API server started")

        yield

    finally:
        # 关闭时清理
        await shutdown_event_bus()
        logger.info("OpenManus API server stopped")


# 创建FastAPI应用
app = FastAPI(
    title="OpenManus API",
    description="OpenManus Agent Execution API with Real-time Tracking",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """根路径 - 返回主页面"""
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "event_bus": event_bus.running if event_bus else False,
        "components": {
            "session_manager": session_manager is not None,
            "execution_manager": execution_manager is not None
        }
    }


@app.post("/api/sessions/start")
async def start_session(request: AgentExecutionRequest):
    """启动新的Agent执行会话"""
    if not session_manager or not event_bus:
        raise HTTPException(status_code=500, detail="Service not initialized")

    try:
        # 发布会话创建请求事件
        create_event = Event(
            event_type=EventType.SESSION_CREATE_REQUEST,
            source="api_handler",
            data={
                "prompt": request.prompt,
                "agent_type": request.agent_type,
                "config": request.config or {},
                "max_steps": request.max_steps,
                "enable_real_time": request.enable_real_time,
                "use_sandbox": request.use_sandbox,
                "sandbox_config": request.sandbox_config or {}
            }
        )

        await event_bus.publish(create_event)

        # 等待会话创建完成
        created_event = await event_bus.wait_for_event(EventType.SESSION_CREATED, timeout=10.0)

        if created_event:
            session_data = created_event.data.get("session", {})
            session_id = session_data.get("session_id")

            return {
                "session_id": session_id,
                "status": "started",
                "websocket_url": f"/ws/{session_id}",
                "request_id": create_event.event_id
            }
        else:
            raise HTTPException(status_code=500, detail="Session creation timeout")

    except Exception as e:
        logging.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    if not session_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.model_dump()


@app.get("/api/sessions")
async def list_sessions(status: Optional[str] = None, limit: int = 50):
    """获取会话列表"""
    if not session_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    sessions = session_manager.list_sessions(status=status)

    # 限制返回数量
    if limit > 0:
        sessions = sessions[:limit]

    return {
        "sessions": [session.model_dump() for session in sessions],
        "total": len(sessions)
    }


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """停止会话执行"""
    if not session_manager or not event_bus:
        raise HTTPException(status_code=500, detail="Service not initialized")

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # 发布停止请求事件
        stop_event = Event(
            event_type=EventType.SESSION_STOP_REQUEST,
            source="api_handler",
            session_id=session_id,
            data={"reason": "user_requested"}
        )

        await event_bus.publish(stop_event)

        return {"status": "stop_requested", "session_id": session_id}

    except Exception as e:
        logging.error(f"Failed to stop session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/continue")
async def continue_session(session_id: str, request: ContinueRequest):
    """继续会话执行（用户输入）"""
    if not session_manager or not event_bus:
        raise HTTPException(status_code=500, detail="Service not initialized")

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # 发布用户输入事件
        input_event = Event(
            event_type=EventType.USER_INPUT,
            source="api_handler",
            session_id=session_id,
            data={
                "user_input": request.user_input,
                "timestamp": "now"
            }
        )

        await event_bus.publish(input_event)

        return {"status": "input_received", "session_id": session_id}

    except Exception as e:
        logging.error(f"Failed to continue session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    stats = {}

    if event_bus:
        stats["event_bus"] = event_bus.get_stats()

    if session_manager:
        stats["session_manager"] = session_manager.get_stats()

    if execution_manager:
        stats["execution_manager"] = execution_manager.get_stats()

    return stats


# WebSocket连接管理
class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """建立WebSocket连接"""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = []

        self.active_connections[session_id].append(websocket)
        logging.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        """断开WebSocket连接"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)

            # 如果没有连接了，清理会话
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        logging.info(f"WebSocket disconnected for session: {session_id}")

    async def send_to_session(self, session_id: str, message: dict):
        """发送消息给特定会话的所有连接"""
        if session_id in self.active_connections:
            connections = self.active_connections[session_id][:]  # 复制列表

            for connection in connections:
                try:
                    await connection.send_json(message)
                except:
                    # 连接已断开，移除
                    self.disconnect(connection, session_id)


# 全局连接管理器
connection_manager = ConnectionManager()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket端点"""
    await connection_manager.connect(websocket, session_id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 处理客户端消息（如用户输入）
            if data.get("type") == "user_input" and event_bus:
                input_event = Event(
                    event_type=EventType.USER_INPUT,
                    source="websocket_client",
                    session_id=session_id,
                    data=data.get("data", {})
                )
                await event_bus.publish(input_event)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, session_id)


# 事件广播处理器
async def broadcast_event_handler(event: Event):
    """处理需要广播的事件"""
    if event.session_id and event.event_type in {
        EventType.SESSION_STARTED,
        EventType.SESSION_STOPPED,
        EventType.SESSION_ERROR,
        EventType.AGENT_STEP_START,
        EventType.AGENT_STEP_END,
        EventType.TOOL_CALL_START,
        EventType.TOOL_CALL_END,
        EventType.TOOL_CALL_ERROR,
        EventType.LLM_CALL_START,
        EventType.LLM_CALL_END,
        EventType.LLM_CALL_ERROR,
        EventType.SANDBOX_COMMAND_START,
        EventType.SANDBOX_COMMAND_OUTPUT,
        EventType.SANDBOX_COMMAND_END,
        EventType.SANDBOX_COMMAND_ERROR,
        EventType.SANDBOX_RESOURCE_USAGE,
        EventType.USER_INPUT,
    }:
        # 准备完整的广播数据
        broadcast_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "source": event.source,
            "target": event.target,
            "session_id": event.session_id,
            "correlation_id": event.correlation_id,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data or {}
        }

        # 广播给对应会话的所有WebSocket连接
        await connection_manager.send_to_session(event.session_id, broadcast_data)


# 事件广播处理器已在lifespan中注册
