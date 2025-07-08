"""
事件类型定义模块
定义了OpenManus系统中所有的事件类型和数据模型
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class EventType(str, Enum):
    """事件类型枚举 - 采用分层命名规范：<组件>.<操作>.<状态>"""
    
    # 会话管理事件
    SESSION_CREATE_REQUEST = "session.create.request"
    SESSION_CREATED = "session.created"
    SESSION_START_REQUEST = "session.start.request"
    SESSION_STARTED = "session.started"
    SESSION_STOP_REQUEST = "session.stop.request"
    SESSION_STOPPED = "session.stopped"
    SESSION_ERROR = "session.error"
    
    # Agent执行事件
    AGENT_STEP_START = "agent.step.start"
    AGENT_STEP_END = "agent.step.end"
    AGENT_THINKING = "agent.thinking"
    AGENT_DECISION = "agent.decision"
    
    # 工具执行事件
    TOOL_CALL_REQUEST = "tool.call.request"
    TOOL_CALL_START = "tool.call.start"
    TOOL_CALL_END = "tool.call.end"
    TOOL_CALL_ERROR = "tool.call.error"
    
    # LLM调用事件
    LLM_CALL_REQUEST = "llm.call.request"
    LLM_CALL_START = "llm.call.start"
    LLM_CALL_END = "llm.call.end"
    LLM_CALL_ERROR = "llm.call.error"
    
    # 沙箱操作事件
    SANDBOX_CREATE_REQUEST = "sandbox.create.request"
    SANDBOX_CREATED = "sandbox.created"
    SANDBOX_START_REQUEST = "sandbox.start.request"
    SANDBOX_STARTED = "sandbox.started"
    SANDBOX_STOP_REQUEST = "sandbox.stop.request"
    SANDBOX_STOPPED = "sandbox.stopped"
    SANDBOX_CLEANUP_REQUEST = "sandbox.cleanup.request"
    SANDBOX_CLEANED = "sandbox.cleaned"
    SANDBOX_ERROR = "sandbox.error"
    
    # 沙箱执行事件
    SANDBOX_COMMAND_REQUEST = "sandbox.command.request"
    SANDBOX_COMMAND_START = "sandbox.command.start"
    SANDBOX_COMMAND_OUTPUT = "sandbox.command.output"
    SANDBOX_COMMAND_END = "sandbox.command.end"
    SANDBOX_COMMAND_ERROR = "sandbox.command.error"
    
    # 沙箱文件操作事件
    SANDBOX_FILE_READ_REQUEST = "sandbox.file.read.request"
    SANDBOX_FILE_READ_RESULT = "sandbox.file.read.result"
    SANDBOX_FILE_WRITE_REQUEST = "sandbox.file.write.request"
    SANDBOX_FILE_WRITE_RESULT = "sandbox.file.write.result"
    SANDBOX_FILE_LIST_REQUEST = "sandbox.file.list.request"
    SANDBOX_FILE_LIST_RESULT = "sandbox.file.list.result"
    
    # 沙箱状态事件
    SANDBOX_STATUS_REQUEST = "sandbox.status.request"
    SANDBOX_STATUS_RESULT = "sandbox.status.result"
    SANDBOX_RESOURCE_USAGE = "sandbox.resource.usage"
    
    # 用户交互事件
    USER_INPUT = "user.input"
    USER_FEEDBACK = "user.feedback"
    
    # 系统事件
    SYSTEM_STATUS = "system.status"
    SYSTEM_ERROR = "system.error"
    
    # 存储事件
    STORE_EVENT = "store.event"
    STORE_SESSION = "store.session"
    
    # 实时广播事件
    BROADCAST_TO_CLIENT = "broadcast.to_client"


class Event(BaseModel):
    """事件数据模型"""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="事件唯一标识")
    event_type: EventType = Field(..., description="事件类型")
    timestamp: datetime = Field(default_factory=datetime.now, description="事件时间戳")
    session_id: Optional[str] = Field(None, description="会话ID")
    source: str = Field(..., description="事件来源组件")
    target: Optional[str] = Field(None, description="目标组件（可选）")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
    correlation_id: Optional[str] = Field(None, description="用于关联相关事件")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionInfo(BaseModel):
    """会话信息模型"""
    
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    agent_name: str = Field(..., description="Agent名称")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    status: str = Field("created", description="会话状态")  # created, running, completed, error, stopped
    total_steps: int = Field(0, description="总步数")
    current_step: int = Field(0, description="当前步数")
    config: Dict[str, Any] = Field(default_factory=dict, description="会话配置")
    result: Optional[str] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentExecutionRequest(BaseModel):
    """Agent执行请求模型"""
    
    prompt: str = Field(..., description="用户输入的任务")
    agent_type: str = Field("manus", description="Agent类型")
    config: Optional[Dict[str, Any]] = Field(None, description="执行配置")
    max_steps: Optional[int] = Field(20, description="最大执行步数")
    enable_real_time: bool = Field(True, description="是否启用实时跟踪")
    use_sandbox: bool = Field(True, description="是否使用沙箱")
    sandbox_config: Optional[Dict[str, Any]] = Field(None, description="沙箱配置")


class ContinueRequest(BaseModel):
    """继续执行请求模型"""
    
    user_input: str = Field(..., description="用户输入")


class EventFilter(BaseModel):
    """事件过滤器模型"""
    
    session_id: Optional[str] = None
    event_types: Optional[list[EventType]] = None
    source: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = Field(1000, description="返回事件数量限制")


# 广播事件类型 - 需要推送给前端的事件
BROADCAST_EVENT_TYPES = {
    EventType.SESSION_STARTED,
    EventType.SESSION_STOPPED,
    EventType.SESSION_ERROR,
    EventType.AGENT_STEP_START,
    EventType.AGENT_STEP_END,
    EventType.AGENT_THINKING,
    EventType.AGENT_DECISION,
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
    EventType.SYSTEM_ERROR,
}


# 存储事件类型 - 需要持久化的事件
STORAGE_EVENT_TYPES = {
    EventType.SESSION_CREATED,
    EventType.SESSION_STARTED,
    EventType.SESSION_STOPPED,
    EventType.SESSION_ERROR,
    EventType.AGENT_STEP_START,
    EventType.AGENT_STEP_END,
    EventType.TOOL_CALL_START,
    EventType.TOOL_CALL_END,
    EventType.LLM_CALL_START,
    EventType.LLM_CALL_END,
    EventType.SANDBOX_COMMAND_START,
    EventType.SANDBOX_COMMAND_END,
    EventType.USER_INPUT,
}
