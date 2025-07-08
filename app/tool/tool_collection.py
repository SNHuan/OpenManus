"""Collection classes for managing multiple tools."""
from typing import Any, Dict, List, Optional

from app.exceptions import ToolError
from app.logger import logger
from app.tool.base import BaseTool, ToolFailure, ToolResult


class ToolCollection:
    """A collection of defined tools."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool, event_bus: Optional[Any] = None, session_id: Optional[str] = None):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.event_bus = event_bus
        self.session_id = session_id

        # 为支持事件总线的工具设置事件总线和会话ID
        self._setup_tools_with_event_bus()

    def __iter__(self):
        return iter(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        return [tool.to_param() for tool in self.tools]

    async def execute(
        self, *, name: str, tool_input: Dict[str, Any] = None
    ) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            result = await tool(**tool_input)
            return result
        except ToolError as e:
            return ToolFailure(error=e.message)

    async def execute_all(self) -> List[ToolResult]:
        """Execute all tools in the collection sequentially."""
        results = []
        for tool in self.tools:
            try:
                result = await tool()
                results.append(result)
            except ToolError as e:
                results.append(ToolFailure(error=e.message))
        return results

    def get_tool(self, name: str) -> BaseTool:
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool):
        """Add a single tool to the collection.

        If a tool with the same name already exists, it will be skipped and a warning will be logged.
        """
        if tool.name in self.tool_map:
            logger.warning(f"Tool {tool.name} already exists in collection, skipping")
            return self

        self.tools += (tool,)
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool):
        """Add multiple tools to the collection.

        If any tool has a name conflict with an existing tool, it will be skipped and a warning will be logged.
        """
        for tool in tools:
            self.add_tool(tool)
        return self

    def _setup_tools_with_event_bus(self):
        """为支持事件总线的工具设置事件总线和会话ID"""
        if not self.event_bus or not self.session_id:
            return

        for tool in self.tools:
            # 检查工具是否支持事件总线
            if hasattr(tool, 'event_bus') and hasattr(tool, 'session_id'):
                # 使用object.__setattr__来绕过Pydantic的字段验证
                object.__setattr__(tool, 'event_bus', self.event_bus)
                object.__setattr__(tool, 'session_id', self.session_id)
                if hasattr(tool, 'use_sandbox'):
                    object.__setattr__(tool, 'use_sandbox', True)

    def set_event_context(self, event_bus: Any, session_id: str):
        """设置事件上下文"""
        self.event_bus = event_bus
        self.session_id = session_id
        self._setup_tools_with_event_bus()
