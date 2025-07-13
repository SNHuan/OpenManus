"""
Browser executor that runs in a separate thread to avoid event loop conflicts.
This module handles the execution of browser operations in an isolated environment.
"""

import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from app.logger import logger
from app.tool.base import ToolResult


class BrowserExecutor:
    """
    Executor for browser operations that runs in a separate thread.
    This avoids event loop conflicts between FastAPI and Playwright.
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")
        self._browser_tool = None

    def _setup_browser_environment(self):
        """Setup browser environment in the executor thread."""
        # Set up Windows-specific event loop policy for browser operations
        if sys.platform == "win32":
            try:
                # Use ProactorEventLoopPolicy for browser operations in this thread
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                logger.debug("Browser thread: ProactorEventLoopPolicy set")
            except Exception as e:
                logger.warning(f"Browser thread: Failed to set event loop policy: {e}")

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Import and create browser tool in this thread
        from app.tool.browser_use_tool import BrowserUseTool
        self._browser_tool = BrowserUseTool()

        return loop

    def _execute_browser_action(self, action: str, **kwargs) -> ToolResult:
        """Execute browser action in the dedicated thread."""
        try:
            # Setup environment if not already done
            if self._browser_tool is None:
                loop = self._setup_browser_environment()
            else:
                loop = asyncio.get_event_loop()

            # Execute the browser action
            result = loop.run_until_complete(
                self._browser_tool.execute(action=action, **kwargs)
            )

            return result

        except Exception as e:
            logger.error(f"Browser action '{action}' failed in executor: {e}")
            return ToolResult(error=f"Browser execution failed: {str(e)}")

    async def execute_action(self, action: str, **kwargs) -> ToolResult:
        """
        Execute browser action asynchronously using the thread executor.

        Args:
            action: Browser action to perform
            **kwargs: Action parameters

        Returns:
            ToolResult with the action's output or error
        """
        try:
            # Create a wrapper function that includes the kwargs
            def execute_with_kwargs():
                return self._execute_browser_action(action, **kwargs)

            # Run browser action in the dedicated thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                execute_with_kwargs
            )

            return result

        except Exception as e:
            logger.error(f"Browser executor failed: {e}")
            return ToolResult(error=f"Browser executor error: {str(e)}")

    async def get_current_state(self) -> ToolResult:
        """Get current browser state."""
        try:
            def _get_state():
                if self._browser_tool is None:
                    loop = self._setup_browser_environment()
                else:
                    loop = asyncio.get_event_loop()

                return loop.run_until_complete(self._browser_tool.get_current_state())

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, _get_state)

            return result

        except Exception as e:
            logger.error(f"Failed to get browser state: {e}")
            return ToolResult(error=f"Browser state error: {str(e)}")

    async def cleanup(self):
        """Clean up browser resources."""
        try:
            def _cleanup():
                if self._browser_tool is not None:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self._browser_tool.cleanup())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, _cleanup)

        except Exception as e:
            logger.error(f"Browser cleanup failed: {e}")
        finally:
            self._executor.shutdown(wait=True)


# Global browser executor instance
_browser_executor: Optional[BrowserExecutor] = None


def get_browser_executor() -> BrowserExecutor:
    """Get the global browser executor instance."""
    global _browser_executor
    if _browser_executor is None:
        _browser_executor = BrowserExecutor()
    return _browser_executor


async def cleanup_browser_executor():
    """Clean up the global browser executor."""
    global _browser_executor
    if _browser_executor is not None:
        await _browser_executor.cleanup()
        _browser_executor = None
