"""
Browser Plugin
Provides web browsing capabilities using Playwright.
Allowed agents to visit URLS, read content, and interact with pages.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
import base64

try:
    from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Fallback types for hints
    Playwright = Any
    Browser = Any
    BrowserContext = Any
    Page = Any

from ..core.plugins import BasePlugin
from ..tools.base import BaseTool, ToolResult
from ..config import config

logger = logging.getLogger(__name__)

class BrowserBaseTool(BaseTool):
    """Base class for browser tools to access the plugin instance"""
    def __init__(self, plugin: "BrowserPlugin"):
        self.plugin = plugin

    def _check_available(self) -> Optional[ToolResult]:
        if not self.plugin.page:
            return ToolResult(success=False, output="Browser is not active or page is not open.")
        return None

class BrowserNavigateTool(BrowserBaseTool):
    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return "Navigate the browser to a specific URL."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to visit (must start with http/https)."}
            },
            "required": ["url"]
        }

    async def execute(self, url: str, **kwargs) -> ToolResult:
        if not self.plugin.page:
           return ToolResult(success=False, output="Browser not initialized.")
        
        try:
            await self.plugin.page.goto(url, timeout=30000)
            title = await self.plugin.page.title()
            return ToolResult(success=True, output=f"Navigated to: {title} ({url})")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to navigate: {str(e)}")

class BrowserContentTool(BrowserBaseTool):
    @property
    def name(self) -> str:
        return "browser_content"

    @property
    def description(self) -> str:
        return "Get the text content of the current page."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        err = self._check_available()
        if err: return err
        
        try:
            # Simple text extraction for now
            # In future, could use Readability.js or similar
            content = await self.plugin.page.evaluate("() => document.body.innerText")
            # Truncate if too long (simple protection)
            return ToolResult(success=True, output=content[:10000]) 
        except Exception as e:
             return ToolResult(success=False, output=f"Failed to read content: {str(e)}")

class BrowserClickTool(BrowserBaseTool):
    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "Click an element on the page using a CSS selector."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object", 
            "properties": {
                "selector": {"type": "string", "description": "CSS selector to click (e.g. '#submit-btn')."}
            },
            "required": ["selector"]
        }

    async def execute(self, selector: str, **kwargs) -> ToolResult:
        err = self._check_available()
        if err: return err

        try:
            await self.plugin.page.click(selector, timeout=5000)
            return ToolResult(success=True, output=f"Clicked element: {selector}")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to click: {str(e)}")

class BrowserScreenshotTool(BrowserBaseTool):
    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return "Take a screenshot of the current page."

    @property
    def parameters(self) -> Dict[str, Any]:
         return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        err = self._check_available()
        if err: return err

        try:
             # Return as base64 for now, or could save to disk
             # For Agent usage, saving to disk and returning path is often better, 
             # but let's just return a success message for now.
             path = f"./data/screenshots/screenshot_{int(asyncio.get_event_loop().time())}.png"
             import os
             os.makedirs(os.path.dirname(path), exist_ok=True)
             
             await self.plugin.page.screenshot(path=path)
             return ToolResult(success=True, output=f"Screenshot saved to {path}")
        except Exception as e:
             return ToolResult(success=False, output=f"Failed to take screenshot: {str(e)}")

class BrowserTypeTool(BrowserBaseTool):
    """Type text into an input element."""
    
    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return """Type text into an input field or textarea.

Use this to fill forms, search boxes, or any text input.
Optionally clear the field first before typing."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the input element (e.g. '#search', 'input[name=q]')."
                },
                "text": {
                    "type": "string",
                    "description": "The text to type into the input."
                },
                "clear": {
                    "type": "boolean",
                    "description": "Clear the field before typing (default: true)."
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Press Enter after typing (default: false)."
                }
            },
            "required": ["selector", "text"]
        }

    async def execute(
        self,
        selector: str,
        text: str,
        clear: bool = True,
        press_enter: bool = False,
        **kwargs
    ) -> ToolResult:
        err = self._check_available()
        if err:
            return err

        try:
            # Focus the element first
            element = await self.plugin.page.wait_for_selector(selector, timeout=5000)
            if not element:
                return ToolResult(success=False, output=f"Element not found: {selector}")
            
            # Clear if requested
            if clear:
                await element.fill("")
            
            # Type the text
            await element.type(text, delay=50)  # Small delay for more natural typing
            
            # Press Enter if requested
            if press_enter:
                await element.press("Enter")
                return ToolResult(
                    success=True,
                    output=f"Typed '{text}' into {selector} and pressed Enter"
                )
            
            return ToolResult(success=True, output=f"Typed '{text}' into {selector}")
            
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to type: {str(e)}")


class BrowserScrollTool(BrowserBaseTool):
    """Scroll the page or an element."""
    
    @property
    def name(self) -> str:
        return "browser_scroll"

    @property
    def description(self) -> str:
        return """Scroll the page up, down, or to a specific element.

Use 'direction' for relative scrolling (up/down/top/bottom).
Use 'selector' to scroll a specific element into view."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "top", "bottom"],
                    "description": "Scroll direction: up, down, top (page start), bottom (page end)."
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector to scroll into view (overrides direction)."
                },
                "amount": {
                    "type": "integer",
                    "description": "Pixels to scroll for up/down (default: 500)."
                }
            }
        }

    async def execute(
        self,
        direction: Optional[str] = None,
        selector: Optional[str] = None,
        amount: int = 500,
        **kwargs
    ) -> ToolResult:
        err = self._check_available()
        if err:
            return err

        try:
            # Scroll to specific element
            if selector:
                element = await self.plugin.page.wait_for_selector(selector, timeout=5000)
                if not element:
                    return ToolResult(success=False, output=f"Element not found: {selector}")
                
                await element.scroll_into_view_if_needed()
                return ToolResult(success=True, output=f"Scrolled to element: {selector}")
            
            # Directional scrolling
            if direction == "top":
                await self.plugin.page.evaluate("window.scrollTo(0, 0)")
                return ToolResult(success=True, output="Scrolled to top of page")
            
            elif direction == "bottom":
                await self.plugin.page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                return ToolResult(success=True, output="Scrolled to bottom of page")
            
            elif direction == "up":
                await self.plugin.page.evaluate(f"window.scrollBy(0, -{amount})")
                return ToolResult(success=True, output=f"Scrolled up {amount}px")
            
            elif direction == "down":
                await self.plugin.page.evaluate(f"window.scrollBy(0, {amount})")
                return ToolResult(success=True, output=f"Scrolled down {amount}px")
            
            else:
                return ToolResult(
                    success=False,
                    output="Specify either 'direction' (up/down/top/bottom) or 'selector'"
                )
                
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to scroll: {str(e)}")


class BrowserPlugin(BasePlugin):
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None

    @property
    def name(self) -> str:
        return "browser"

    async def on_load(self):
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not installed. Browser plugin disabled.")
            return

        try:
            self.playwright = await async_playwright().start()
            
            # Load config
            # Safe access to config.browser
            b_conf = getattr(config, 'browser', {})
            # If it's a Pydantic model
            if hasattr(b_conf, 'headless'):
                headless = b_conf.headless
                viewport = b_conf.viewport
            else: # fallback dict
                headless = True
                viewport = {"width": 1280, "height": 720}

            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(
                viewport=viewport,
                user_agent="AgentPlatform/1.0"
            )
            self.page = await self.context.new_page()
            logger.info("Browser Plugin initialized (Chromium)")
            
        except Exception as e:
            logger.error(f"Failed to initialize Browser Plugin: {e}", exc_info=True)
            await self.cleanup()

    async def cleanup(self):
        if self.page: await self.page.close()
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def get_tools(self) -> List[BaseTool]:
        return [
            BrowserNavigateTool(self),
            BrowserContentTool(self),
            BrowserClickTool(self),
            BrowserTypeTool(self),
            BrowserScrollTool(self),
            BrowserScreenshotTool(self)
        ]
