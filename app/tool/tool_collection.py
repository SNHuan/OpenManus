"""Collection classes for managing multiple tools."""
import time
from typing import Any, Dict, List, Optional

from app.exceptions import ToolError
from app.logger import logger
from app.tool.base import BaseTool, ToolFailure, ToolResult
from app.event import EventAwareMixin, create_tool_execution_event, ToolExecutionStatus


class ToolCollection(EventAwareMixin):
    """A collection of defined tools."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool, conversation_id: Optional[str] = None):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.conversation_id = conversation_id

    def __iter__(self):
        return iter(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        return [tool.to_param() for tool in self.tools]

    async def execute(
        self, *, name: str, tool_input: Dict[str, Any] = None
    ) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            # Publish tool not found event
            await self.publish_error(
                error_type="ToolNotFound",
                error_message=f"Tool {name} is invalid",
                context={"tool_name": name, "available_tools": list(self.tool_map.keys())}
            )
            return ToolFailure(error=f"Tool {name} is invalid")

        # Record start time for execution metrics
        start_time = time.time()

        # Publish tool execution start event
        await self.publish_event(create_tool_execution_event(
            tool_name=name,
            tool_type=tool.__class__.__name__,
            status="started",
            parameters=tool_input or {},
            conversation_id=self.conversation_id
        ))

        try:
            result = await tool(**(tool_input or {}))
            execution_time = time.time() - start_time

            # Publish tool execution success event
            await self.publish_event(create_tool_execution_event(
                tool_name=name,
                tool_type=tool.__class__.__name__,
                status="completed",
                parameters=tool_input or {},
                conversation_id=self.conversation_id
            ))

            # Log execution metrics
            logger.debug(f"Tool '{name}' executed successfully in {execution_time:.2f}s")

            return result

        except ToolError as e:
            execution_time = time.time() - start_time

            # Publish tool execution failure event
            await self.publish_event(create_tool_execution_event(
                tool_name=name,
                tool_type=tool.__class__.__name__,
                status="failed",
                parameters=tool_input or {},
                conversation_id=self.conversation_id
            ))

            # Publish error event
            await self.publish_error(
                error_type="ToolExecutionError",
                error_message=e.message,
                context={
                    "tool_name": name,
                    "tool_input": tool_input,
                    "execution_time": execution_time
                }
            )

            return ToolFailure(error=e.message)

        except Exception as e:
            execution_time = time.time() - start_time

            # Publish unexpected error event
            await self.publish_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={
                    "tool_name": name,
                    "tool_input": tool_input,
                    "execution_time": execution_time
                }
            )

            return ToolFailure(error=f"Unexpected error: {str(e)}")

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
