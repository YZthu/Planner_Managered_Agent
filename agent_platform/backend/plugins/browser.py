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
            BrowserScreenshotTool(self)
        ]
