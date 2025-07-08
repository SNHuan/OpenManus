"""
沙箱事件管理器

负责处理沙箱相关的事件，包括命令执行、文件操作等，
并将沙箱的实时输出通过事件总线发送到前端。
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from app.events.types import Event, EventType
from app.events.bus import EventBus
from app.sandbox.core.manager import SandboxManager
from app.sandbox.core.sandbox import DockerSandbox
from app.sandbox.core.terminal import AsyncDockerizedTerminal


class SandboxEventManager:
    """沙箱事件管理器

    处理沙箱相关的事件，包括：
    - 命令执行和实时输出
    - 文件操作
    - 资源监控
    """

    def __init__(self, event_bus: EventBus, sandbox_manager: SandboxManager):
        self.event_bus = event_bus
        self.sandbox_manager = sandbox_manager
        self.logger = logging.getLogger(__name__)
        self.component_name = "sandbox_event_manager"

        # 会话到沙箱的映射
        self.session_sandboxes: Dict[str, str] = {}

        # 订阅相关事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅沙箱相关事件"""
        # 沙箱操作事件
        self.event_bus.subscribe(EventType.SANDBOX_CREATE_REQUEST, self._handle_create_sandbox)
        self.event_bus.subscribe(EventType.SANDBOX_COMMAND_REQUEST, self._handle_command_request)
        self.event_bus.subscribe(EventType.SANDBOX_FILE_READ_REQUEST, self._handle_file_read)
        self.event_bus.subscribe(EventType.SANDBOX_FILE_WRITE_REQUEST, self._handle_file_write)
        self.event_bus.subscribe(EventType.SANDBOX_CLEANUP_REQUEST, self._handle_cleanup_sandbox)

        # 会话结束时清理沙箱
        self.event_bus.subscribe(EventType.SESSION_STOPPED, self._handle_session_stopped)

    async def _handle_create_sandbox(self, event: Event):
        """处理沙箱创建请求"""
        session_id = event.session_id

        try:
            self.logger.info(f"Creating sandbox for session: {session_id}")

            # 检查Docker是否可用
            if not self.sandbox_manager._docker_available:
                self.logger.warning(f"Docker not available for session {session_id}, skipping sandbox creation")

                # 发布警告事件，但不阻止会话继续
                warning_event = Event(
                    event_type=EventType.SANDBOX_ERROR,
                    source=self.component_name,
                    session_id=session_id,
                    correlation_id=event.correlation_id,
                    data={
                        "error": "Docker is not available. Sandbox features will be disabled. Python code will run locally.",
                        "operation": "create",
                        "severity": "warning"
                    }
                )
                await self.event_bus.publish(warning_event)

                # 发布一个模拟的沙箱输出，告知用户Docker不可用
                output_event = Event(
                    event_type=EventType.SANDBOX_COMMAND_OUTPUT,
                    source=self.component_name,
                    session_id=session_id,
                    correlation_id=event.correlation_id,
                    data={
                        "content": "⚠️ Docker is not available. Python code will run locally instead of in sandbox.",
                        "output_type": "warning"
                    }
                )
                await self.event_bus.publish(output_event)
                return

            # 创建沙箱
            sandbox_id = await self.sandbox_manager.create_sandbox()
            self.session_sandboxes[session_id] = sandbox_id

            # 发布创建成功事件
            created_event = Event(
                event_type=EventType.SANDBOX_CREATED,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "sandbox_id": sandbox_id,
                    "status": "created"
                }
            )
            await self.event_bus.publish(created_event)

            self.logger.info(f"Sandbox {sandbox_id} created for session {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to create sandbox for session {session_id}: {e}")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SANDBOX_ERROR,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "error": str(e),
                    "operation": "create"
                }
            )
            await self.event_bus.publish(error_event)

    async def _handle_command_request(self, event: Event):
        """处理命令执行请求"""
        session_id = event.session_id
        command = event.data.get("command", "")
        timeout = event.data.get("timeout", 120)

        self.logger.info(f"Handling command request for session {session_id}: {command}")

        if not command:
            self.logger.warning(f"Empty command for session {session_id}")
            return

        sandbox_id = self.session_sandboxes.get(session_id)
        if not sandbox_id:
            self.logger.warning(f"No sandbox found for session {session_id}, command will not be executed")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SANDBOX_COMMAND_ERROR,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "command": command,
                    "error": "No sandbox available. Docker may not be running.",
                    "sandbox_id": None
                }
            )
            await self.event_bus.publish(error_event)
            return

        try:
            # 发布命令开始事件
            self.logger.info(f"Publishing SANDBOX_COMMAND_START event for session {session_id}")
            start_event = Event(
                event_type=EventType.SANDBOX_COMMAND_START,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "command": command,
                    "sandbox_id": sandbox_id
                }
            )
            await self.event_bus.publish(start_event)

            # 执行命令并捕获实时输出
            self.logger.info(f"Starting command execution for session {session_id}")
            async with self.sandbox_manager.sandbox_operation(sandbox_id) as sandbox:
                output = await self._execute_command_with_streaming(
                    sandbox, command, session_id, event.correlation_id, timeout
                )
                self.logger.info(f"Command execution completed for session {session_id}, output length: {len(output) if output else 0}")

            # 发布命令结束事件
            end_event = Event(
                event_type=EventType.SANDBOX_COMMAND_END,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "command": command,
                    "output": output,
                    "exit_code": 0,  # 简化处理，假设成功
                    "sandbox_id": sandbox_id
                }
            )
            await self.event_bus.publish(end_event)

        except Exception as e:
            self.logger.error(f"Command execution failed for session {session_id}: {e}")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SANDBOX_COMMAND_ERROR,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "command": command,
                    "error": str(e),
                    "sandbox_id": sandbox_id
                }
            )
            await self.event_bus.publish(error_event)

    async def _execute_command_with_streaming(
        self,
        sandbox: DockerSandbox,
        command: str,
        session_id: str,
        correlation_id: str,
        timeout: int = 120
    ) -> str:
        """执行命令并实时发送输出事件"""
        if not sandbox.terminal:
            raise RuntimeError("Sandbox terminal not initialized")

        # 这里我们需要修改terminal的execute方法来支持流式输出
        # 目前先使用现有的方法，后续可以优化
        try:
            output = await sandbox.run_command(command, timeout)

            # 发布输出事件
            self.logger.info(f"Command output for session {session_id}: '{output}' (length: {len(output) if output else 0})")
            if output and output.strip():
                self.logger.info(f"Publishing SANDBOX_COMMAND_OUTPUT event for session {session_id}")
                output_event = Event(
                    event_type=EventType.SANDBOX_COMMAND_OUTPUT,
                    source=self.component_name,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    data={
                        "command": command,
                        "content": output,
                        "output_type": "stdout"
                    }
                )
                await self.event_bus.publish(output_event)
            else:
                self.logger.warning(f"No output to publish for session {session_id}")

            return output

        except Exception as e:
            # 发布错误输出
            error_output_event = Event(
                event_type=EventType.SANDBOX_COMMAND_OUTPUT,
                source=self.component_name,
                session_id=session_id,
                correlation_id=correlation_id,
                data={
                    "command": command,
                    "content": str(e),
                    "output_type": "stderr"
                }
            )
            await self.event_bus.publish(error_output_event)
            raise

    async def _handle_file_read(self, event: Event):
        """处理文件读取请求"""
        session_id = event.session_id
        file_path = event.data.get("file_path", "")

        sandbox_id = self.session_sandboxes.get(session_id)
        if not sandbox_id:
            self.logger.error(f"No sandbox found for session {session_id}")
            return

        try:
            async with self.sandbox_manager.sandbox_operation(sandbox_id) as sandbox:
                # 使用cat命令读取文件
                content = await sandbox.run_command(f"cat '{file_path}'")

            # 发布读取结果事件
            result_event = Event(
                event_type=EventType.SANDBOX_FILE_READ_RESULT,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "file_path": file_path,
                    "content": content,
                    "success": True
                }
            )
            await self.event_bus.publish(result_event)

        except Exception as e:
            self.logger.error(f"File read failed for session {session_id}: {e}")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SANDBOX_FILE_READ_RESULT,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "file_path": file_path,
                    "error": str(e),
                    "success": False
                }
            )
            await self.event_bus.publish(error_event)

    async def _handle_file_write(self, event: Event):
        """处理文件写入请求"""
        session_id = event.session_id
        file_path = event.data.get("file_path", "")
        content = event.data.get("content", "")

        sandbox_id = self.session_sandboxes.get(session_id)
        if not sandbox_id:
            self.logger.error(f"No sandbox found for session {session_id}")
            return

        try:
            async with self.sandbox_manager.sandbox_operation(sandbox_id) as sandbox:
                # 使用echo命令写入文件（简化实现）
                escaped_content = content.replace("'", "'\"'\"'")
                await sandbox.run_command(f"echo '{escaped_content}' > '{file_path}'")

            # 发布写入结果事件
            result_event = Event(
                event_type=EventType.SANDBOX_FILE_WRITE_RESULT,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "file_path": file_path,
                    "success": True
                }
            )
            await self.event_bus.publish(result_event)

        except Exception as e:
            self.logger.error(f"File write failed for session {session_id}: {e}")

            # 发布错误事件
            error_event = Event(
                event_type=EventType.SANDBOX_FILE_WRITE_RESULT,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "file_path": file_path,
                    "error": str(e),
                    "success": False
                }
            )
            await self.event_bus.publish(error_event)

    async def _handle_cleanup_sandbox(self, event: Event):
        """处理沙箱清理请求"""
        session_id = event.session_id

        sandbox_id = self.session_sandboxes.get(session_id)
        if not sandbox_id:
            self.logger.warning(f"No sandbox to cleanup for session {session_id}")
            return

        try:
            await self.sandbox_manager.delete_sandbox(sandbox_id)
            del self.session_sandboxes[session_id]

            # 发布清理完成事件
            cleaned_event = Event(
                event_type=EventType.SANDBOX_CLEANED,
                source=self.component_name,
                session_id=session_id,
                correlation_id=event.correlation_id,
                data={
                    "sandbox_id": sandbox_id,
                    "status": "cleaned"
                }
            )
            await self.event_bus.publish(cleaned_event)

            self.logger.info(f"Sandbox {sandbox_id} cleaned for session {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to cleanup sandbox for session {session_id}: {e}")

    async def _handle_session_stopped(self, event: Event):
        """处理会话停止事件，自动清理沙箱"""
        session_id = event.session_id

        if session_id in self.session_sandboxes:
            cleanup_event = Event(
                event_type=EventType.SANDBOX_CLEANUP_REQUEST,
                source=self.component_name,
                session_id=session_id,
                data={}
            )
            await self.event_bus.publish(cleanup_event)
