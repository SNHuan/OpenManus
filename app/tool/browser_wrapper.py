"""
Browser tool wrapper that uses the browser executor to avoid event loop conflicts.
This is the main browser tool that should be used by agents.
"""

from typing import Optional
from pydantic import Field

from app.tool.base import BaseTool, ToolResult
from app.tool.browser_executor import get_browser_executor


class BrowserTool(BaseTool):
    """
    Browser tool wrapper that uses the browser executor.
    This tool provides browser automation capabilities while avoiding
    event loop conflicts in multi-threaded environments.
    """
    
    name: str = "browser_use"
    description: str = """\
A powerful browser automation tool that allows interaction with web pages through various actions.
* This tool provides commands for controlling a browser session, navigating web pages, and extracting information
* It maintains state across calls, keeping the browser session alive until explicitly closed
* Use this when you need to browse websites, fill forms, click buttons, extract content, or perform web searches
* Each action requires specific parameters as defined in the tool's dependencies

Key capabilities include:
* Navigation: Go to specific URLs, go back, search the web, or refresh pages
* Interaction: Click elements, input text, select from dropdowns, send keyboard commands
* Scrolling: Scroll up/down by pixel amount or scroll to specific text
* Content extraction: Extract and analyze content from web pages based on specific goals
* Tab management: Switch between tabs, open new tabs, or close tabs

Note: When using element indices, refer to the numbered elements shown in the current browser state.
"""
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "go_to_url",
                    "click_element",
                    "input_text",
                    "scroll_down",
                    "scroll_up",
                    "scroll_to_text",
                    "send_keys",
                    "get_dropdown_options",
                    "select_dropdown_option",
                    "go_back",
                    "web_search",
                    "wait",
                    "extract_content",
                    "switch_tab",
                    "open_tab",
                    "close_tab",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL for 'go_to_url' or 'open_tab' actions",
            },
            "index": {
                "type": "integer",
                "description": "Element index for 'click_element', 'input_text', 'get_dropdown_options', or 'select_dropdown_option' actions",
            },
            "text": {
                "type": "string",
                "description": "Text for 'input_text', 'scroll_to_text', or 'select_dropdown_option' actions",
            },
            "scroll_amount": {
                "type": "integer",
                "description": "Pixels to scroll (positive for down, negative for up) for 'scroll_down' or 'scroll_up' actions",
            },
            "tab_id": {
                "type": "integer",
                "description": "Tab ID for 'switch_tab' action",
            },
            "query": {
                "type": "string",
                "description": "Search query for 'web_search' action",
            },
            "goal": {
                "type": "string",
                "description": "Extraction goal for 'extract_content' action",
            },
            "keys": {
                "type": "string",
                "description": "Keys to send for 'send_keys' action",
            },
            "seconds": {
                "type": "integer",
                "description": "Seconds to wait for 'wait' action",
            },
        },
        "required": ["action"],
        "dependencies": {
            "go_to_url": ["url"],
            "click_element": ["index"],
            "input_text": ["index", "text"],
            "switch_tab": ["tab_id"],
            "open_tab": ["url"],
            "scroll_down": ["scroll_amount"],
            "scroll_up": ["scroll_amount"],
            "scroll_to_text": ["text"],
            "send_keys": ["keys"],
            "get_dropdown_options": ["index"],
            "select_dropdown_option": ["index", "text"],
            "go_back": [],
            "web_search": ["query"],
            "wait": ["seconds"],
            "extract_content": ["goal"],
        },
    }
    
    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        index: Optional[int] = None,
        text: Optional[str] = None,
        scroll_amount: Optional[int] = None,
        tab_id: Optional[int] = None,
        query: Optional[str] = None,
        goal: Optional[str] = None,
        keys: Optional[str] = None,
        seconds: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute a specified browser action using the browser executor.
        
        Args:
            action: The browser action to perform
            url: URL for navigation or new tab
            index: Element index for click or input actions
            text: Text for input action or search query
            scroll_amount: Pixels to scroll for scroll action
            tab_id: Tab ID for switch_tab action
            query: Search query for Google search
            goal: Extraction goal for content extraction
            keys: Keys to send for keyboard actions
            seconds: Seconds to wait
            **kwargs: Additional arguments
            
        Returns:
            ToolResult with the action's output or error
        """
        try:
            executor = get_browser_executor()
            
            # Prepare arguments for the executor
            action_kwargs = {}
            if url is not None:
                action_kwargs["url"] = url
            if index is not None:
                action_kwargs["index"] = index
            if text is not None:
                action_kwargs["text"] = text
            if scroll_amount is not None:
                action_kwargs["scroll_amount"] = scroll_amount
            if tab_id is not None:
                action_kwargs["tab_id"] = tab_id
            if query is not None:
                action_kwargs["query"] = query
            if goal is not None:
                action_kwargs["goal"] = goal
            if keys is not None:
                action_kwargs["keys"] = keys
            if seconds is not None:
                action_kwargs["seconds"] = seconds
            
            # Execute the action using the browser executor
            result = await executor.execute_action(action, **action_kwargs)
            
            return result
            
        except Exception as e:
            return ToolResult(error=f"Browser tool execution failed: {str(e)}")
    
    async def get_current_state(self) -> ToolResult:
        """Get the current browser state."""
        try:
            executor = get_browser_executor()
            return await executor.get_current_state()
        except Exception as e:
            return ToolResult(error=f"Failed to get browser state: {str(e)}")
    
    async def cleanup(self):
        """Clean up browser resources."""
        try:
            from app.tool.browser_executor import cleanup_browser_executor
            await cleanup_browser_executor()
        except Exception as e:
            # Log error but don't raise to avoid breaking cleanup chains
            from app.logger import logger
            logger.error(f"Browser cleanup failed: {e}")


# Create an alias for backward compatibility
BrowserUseTool = BrowserTool
