import multiprocessing
import sys
import asyncio
import uuid
from io import StringIO
from typing import Dict, Optional

from app.tool.base import BaseTool
from app.events.types import Event, EventType
from app.events.bus import EventBus


class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = "Executes Python code string in sandbox environment. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results."
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
        },
        "required": ["code"],
    }

    # 添加可选的事件总线字段
    event_bus: Optional[EventBus] = None
    session_id: Optional[str] = None
    use_sandbox: bool = False

    def _run_code(self, code: str, result_dict: dict, safe_globals: dict) -> None:
        original_stdout = sys.stdout
        try:
            output_buffer = StringIO()
            sys.stdout = output_buffer
            exec(code, safe_globals, safe_globals)
            result_dict["observation"] = output_buffer.getvalue()
            result_dict["success"] = True
        except Exception as e:
            result_dict["observation"] = str(e)
            result_dict["success"] = False
        finally:
            sys.stdout = original_stdout

    async def execute(
        self,
        code: str,
        timeout: int = 120,
    ) -> Dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            timeout (int): Execution timeout in seconds.

        Returns:
            Dict: Contains 'output' with execution output or error message and 'success' status.
        """

        if self.use_sandbox:
            return await self._execute_in_sandbox(code, timeout)
        else:
            return await self._execute_locally(code, timeout)

    async def _execute_in_sandbox(self, code: str, timeout: int) -> Dict:
        """在沙箱中执行Python代码"""
        if not self.event_bus or not self.session_id:
            return {
                "observation": "Sandbox not available",
                "success": False,
            }

        try:
            # 创建临时Python文件
            temp_file = f"/tmp/python_code_{uuid.uuid4().hex[:8]}.py"

            # 写入代码到文件
            write_event = Event(
                event_type=EventType.SANDBOX_FILE_WRITE_REQUEST,
                source="python_execute_tool",
                session_id=self.session_id,
                data={
                    "file_path": temp_file,
                    "content": code
                }
            )
            await self.event_bus.publish(write_event)

            # 等待文件写入完成
            await asyncio.sleep(0.5)

            # 执行Python文件
            command_event = Event(
                event_type=EventType.SANDBOX_COMMAND_REQUEST,
                source="python_execute_tool",
                session_id=self.session_id,
                data={
                    "command": f"cd /tmp && python3 {temp_file}",
                    "timeout": timeout
                }
            )
            await self.event_bus.publish(command_event)

            # 等待命令执行完成
            # 这里简化处理，实际应该监听命令完成事件
            await asyncio.sleep(min(timeout, 10))

            return {
                "observation": "Python code executed in sandbox. Check sandbox output for results.",
                "success": True,
            }

        except Exception as e:
            return {
                "observation": f"Sandbox execution error: {str(e)}",
                "success": False,
            }

    async def _execute_locally(self, code: str, timeout: int) -> Dict:
        """本地执行Python代码（原有逻辑）"""
        with multiprocessing.Manager() as manager:
            result = manager.dict({"observation": "", "success": False})
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": __builtins__}
            else:
                safe_globals = {"__builtins__": __builtins__.__dict__.copy()}
            proc = multiprocessing.Process(
                target=self._run_code, args=(code, result, safe_globals)
            )
            proc.start()
            proc.join(timeout)

            # timeout process
            if proc.is_alive():
                proc.terminate()
                proc.join(1)
                return {
                    "observation": f"Execution timeout after {timeout} seconds",
                    "success": False,
                }
            return dict(result)
