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


class BrowserSnapshotTool(BrowserBaseTool):
    """Get AI-formatted DOM snapshot with element references."""
    
    @property
    def name(self) -> str:
        return "browser_snapshot"

    @property
    def description(self) -> str:
        return """Get a structured snapshot of the current page for reliable element targeting.

Returns a simplified DOM tree with:
- Element references ([1], [2], etc.) that can be used for clicking/typing
- Element types (button, link, input, text)
- Visible text content

This is more reliable than CSS selectors for complex pages."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_elements": {
                    "type": "integer",
                    "description": "Maximum number of interactive elements to include (default: 50)"
                }
            }
        }

    async def execute(self, max_elements: int = 50, **kwargs) -> ToolResult:
        err = self._check_available()
        if err:
            return err

        try:
            # JavaScript to extract interactive elements with references
            snapshot_js = """
            (maxElements) => {
                const elements = [];
                const interactiveSelectors = 'a, button, input, textarea, select, [role="button"], [onclick]';
                const nodes = document.querySelectorAll(interactiveSelectors);
                
                let refNum = 1;
                for (let idx = 0; idx < nodes.length && refNum <= maxElements; idx++) {
                    const el = nodes[idx];
                    
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    
                    const tagName = el.tagName.toLowerCase();
                    let type = tagName;
                    if (tagName === 'a') type = 'link';
                    if (tagName === 'input') type = el.type || 'text';
                    
                    const text = (el.innerText || el.value || el.placeholder || el.alt || el.title || '').slice(0, 100).trim();
                    
                    if (text || ['input', 'textarea', 'button'].includes(tagName)) {
                        elements.push({
                            ref: refNum++,
                            type: type,
                            text: text,
                            selector: el.id ? `#${el.id}` : null
                        });
                    }
                }
                
                return elements;
            }
            """
            
            elements = await self.plugin.page.evaluate(f"({snapshot_js})({max_elements})")
            
            # Format output
            title = await self.plugin.page.title()
            url = self.plugin.page.url
            
            output_lines = [f"Page: {title}", f"URL: {url}", "", "Interactive Elements:"]
            
            for el in elements:
                ref = el['ref']
                el_type = el['type']
                text = el['text'][:60] if el['text'] else '(empty)'
                output_lines.append(f"[{ref}] {el_type}: {text}")
            
            # Store element refs for later use
            self.plugin._element_refs = {el['ref']: el.get('selector') for el in elements}
            
            return ToolResult(
                success=True, 
                output="\n".join(output_lines),
                data={"elements": elements, "count": len(elements)}
            )
            
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to get snapshot: {str(e)}")


class BrowserTabsTool(BrowserBaseTool):
    """List and manage browser tabs."""
    
    @property
    def name(self) -> str:
        return "browser_tabs"

    @property
    def description(self) -> str:
        return """List open browser tabs or switch to a specific tab.

Actions:
- list: Show all open tabs with their titles and URLs
- switch: Switch to a specific tab by index
- new: Open a new tab
- close: Close a tab by index"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "switch", "new", "close"],
                    "description": "Action to perform (default: list)"
                },
                "index": {
                    "type": "integer",
                    "description": "Tab index for switch/close actions (0-based)"
                }
            }
        }

    async def execute(
        self,
        action: str = "list",
        index: Optional[int] = None,
        **kwargs
    ) -> ToolResult:
        if not self.plugin.context:
            return ToolResult(success=False, output="Browser context not available.")

        try:
            pages = self.plugin.context.pages
            
            if action == "list":
                if not pages:
                    return ToolResult(success=True, output="No tabs open.")
                
                lines = ["Open Tabs:"]
                for i, page in enumerate(pages):
                    title = await page.title()
                    url = page.url
                    current = " (current)" if page == self.plugin.page else ""
                    lines.append(f"[{i}] {title}{current}\n    {url}")
                
                return ToolResult(success=True, output="\n".join(lines))
            
            elif action == "switch":
                if index is None or index < 0 or index >= len(pages):
                    return ToolResult(success=False, output=f"Invalid tab index. Have {len(pages)} tabs (0-{len(pages)-1}).")
                
                self.plugin.page = pages[index]
                title = await self.plugin.page.title()
                return ToolResult(success=True, output=f"Switched to tab [{index}]: {title}")
            
            elif action == "new":
                new_page = await self.plugin.context.new_page()
                self.plugin.page = new_page
                return ToolResult(success=True, output=f"Opened new tab [{len(pages)}]")
            
            elif action == "close":
                if index is None:
                    index = len(pages) - 1
                if index < 0 or index >= len(pages):
                    return ToolResult(success=False, output=f"Invalid tab index.")
                
                page_to_close = pages[index]
                await page_to_close.close()
                
                # Switch to another tab if we closed current
                remaining = self.plugin.context.pages
                if remaining:
                    self.plugin.page = remaining[0]
                else:
                    self.plugin.page = await self.plugin.context.new_page()
                
                return ToolResult(success=True, output=f"Closed tab [{index}]")
            
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(success=False, output=f"Tab operation failed: {str(e)}")


class BrowserConsoleTool(BrowserBaseTool):
    """Read browser console logs."""
    
    @property
    def name(self) -> str:
        return "browser_console"

    @property
    def description(self) -> str:
        return """Read console messages from the browser.

Returns recent console.log, console.error, console.warn messages.
Useful for debugging page issues or extracting data logged by scripts."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_messages": {
                    "type": "integer",
                    "description": "Maximum number of messages to return (default: 20)"
                },
                "level": {
                    "type": "string",
                    "enum": ["all", "error", "warning", "log"],
                    "description": "Filter by message level (default: all)"
                }
            }
        }

    async def execute(
        self,
        max_messages: int = 20,
        level: str = "all",
        **kwargs
    ) -> ToolResult:
        err = self._check_available()
        if err:
            return err

        try:
            # Get console messages from plugin's stored messages
            messages = getattr(self.plugin, '_console_messages', [])
            
            if level != "all":
                messages = [m for m in messages if m.get('level') == level]
            
            messages = messages[-max_messages:]
            
            if not messages:
                return ToolResult(
                    success=True,
                    output="No console messages captured. Note: Messages are captured after page load.",
                    data={"messages": []}
                )
            
            lines = ["Console Messages:"]
            for msg in messages:
                lvl = msg.get('level', 'log').upper()
                text = msg.get('text', '')[:200]
                lines.append(f"[{lvl}] {text}")
            
            return ToolResult(success=True, output="\n".join(lines), data={"messages": messages})
            
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to get console: {str(e)}")


class BrowserPDFTool(BrowserBaseTool):
    """Save current page as PDF."""
    
    @property
    def name(self) -> str:
        return "browser_pdf"

    @property
    def description(self) -> str:
        return """Save the current page as a PDF file.

Creates a PDF of the full page content. Useful for archiving or offline reading."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename (default: auto-generated from title)"
                },
                "full_page": {
                    "type": "boolean",
                    "description": "Include full scrollable content (default: true)"
                }
            }
        }

    async def execute(
        self,
        filename: Optional[str] = None,
        full_page: bool = True,
        **kwargs
    ) -> ToolResult:
        err = self._check_available()
        if err:
            return err

        try:
            import os
            import re
            
            # Generate filename from title if not provided
            if not filename:
                title = await self.plugin.page.title()
                # Sanitize title for filename
                safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip()
                filename = f"{safe_title or 'page'}_{int(asyncio.get_event_loop().time())}.pdf"
            
            # Ensure .pdf extension
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            # Create output directory
            pdf_dir = "./data/pdfs"
            os.makedirs(pdf_dir, exist_ok=True)
            path = os.path.join(pdf_dir, filename)
            
            # Generate PDF
            await self.plugin.page.pdf(
                path=path,
                format="A4",
                print_background=True
            )
            
            return ToolResult(
                success=True,
                output=f"Saved PDF to: {path}",
                data={"path": path, "filename": filename}
            )
            
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to save PDF: {str(e)}")


class BrowserPlugin(BasePlugin):
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    _console_messages: List[Dict[str, str]] = []
    _element_refs: Dict[int, str] = {}

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
            
            # Set up console message capture
            self._console_messages = []
            self.page.on("console", lambda msg: self._console_messages.append({
                "level": msg.type,
                "text": msg.text
            }))
            
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
        self._console_messages = []
        self._element_refs = {}

    def get_tools(self) -> List[BaseTool]:
        return [
            BrowserNavigateTool(self),
            BrowserContentTool(self),
            BrowserClickTool(self),
            BrowserTypeTool(self),
            BrowserScrollTool(self),
            BrowserSnapshotTool(self),
            BrowserTabsTool(self),
            BrowserConsoleTool(self),
            BrowserPDFTool(self),
            BrowserScreenshotTool(self)
        ]
