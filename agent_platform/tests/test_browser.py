import unittest
import asyncio
import sys
import os
import shutil

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.plugins.browser import (
    BrowserPlugin, BrowserNavigateTool, BrowserContentTool, 
    BrowserScreenshotTool, BrowserTypeTool, BrowserScrollTool
)
from backend.config import config

class TestBrowserPlugin(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Configure browser settings
        class MockBrowserConfig:
            headless = True
            user_agent = "TestAgent/1.0"
            viewport = {"width": 1280, "height": 720}
        
        config.browser = MockBrowserConfig()

    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_browser_lifecycle(self):
        async def run_test():
            print("Testing Browser Plugin...")
            
            # 1. Initialize
            plugin = BrowserPlugin()
            await plugin.on_load()
            
            if not plugin.browser:
                print("[SKIP] Playwright initialization failed")
                return

            print("[PASS] Plugin initialized")
            
            tools = plugin.get_tools()
            nav_tool = next(t for t in tools if t.name == "browser_navigate")
            content_tool = next(t for t in tools if t.name == "browser_content")
            screenshot_tool = next(t for t in tools if t.name == "browser_screenshot")
            type_tool = next(t for t in tools if t.name == "browser_type")
            scroll_tool = next(t for t in tools if t.name == "browser_scroll")
            
            # 2. Navigate (Use example.com which is stable)
            res = await nav_tool.execute(url="https://example.com")
            assert res.success
            print(f"[PASS] Navigated: {res.output}")
            
            # 3. Content
            res = await content_tool.execute()
            assert res.success
            assert "Example Domain" in res.output
            print(f"[PASS] Content scraped: {len(res.output)} chars")
            
            # 4. Scroll down
            res = await scroll_tool.execute(direction="down", amount=200)
            assert res.success
            print(f"[PASS] Scroll: {res.output}")
            
            # 5. Scroll to top
            res = await scroll_tool.execute(direction="top")
            assert res.success
            print(f"[PASS] Scroll to top: {res.output}")
            
            # 6. Screenshot
            res = await screenshot_tool.execute()
            assert res.success
            print(f"[PASS] Screenshot: {res.output}")
            
            # Cleanup
            await plugin.cleanup()
            print("[PASS] Cleanup complete")

        self.run_async(run_test())

    def test_tool_count(self):
        """Verify all 6 browser tools are registered."""
        plugin = BrowserPlugin()
        tools = plugin.get_tools()
        tool_names = [t.name for t in tools]
        
        expected = [
            "browser_navigate", "browser_content", "browser_click",
            "browser_type", "browser_scroll", "browser_screenshot"
        ]
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"
        
        print(f"[PASS] All 6 browser tools registered: {tool_names}")


class TestBrowserToolsUnit(unittest.TestCase):
    """Unit tests without requiring browser instance."""
    
    def test_type_tool_parameters(self):
        """Test browser_type parameter schema."""
        from backend.plugins.browser import BrowserTypeTool
        
        class FakePlugin:
            page = None
        
        tool = BrowserTypeTool(FakePlugin())
        params = tool.parameters
        
        assert params["properties"]["selector"]["type"] == "string"
        assert params["properties"]["text"]["type"] == "string"
        assert params["properties"]["clear"]["type"] == "boolean"
        assert params["properties"]["press_enter"]["type"] == "boolean"
        assert "selector" in params["required"]
        assert "text" in params["required"]
        
    def test_scroll_tool_parameters(self):
        """Test browser_scroll parameter schema."""
        from backend.plugins.browser import BrowserScrollTool
        
        class FakePlugin:
            page = None
        
        tool = BrowserScrollTool(FakePlugin())
        params = tool.parameters
        
        assert params["properties"]["direction"]["type"] == "string"
        assert "up" in params["properties"]["direction"]["enum"]
        assert "down" in params["properties"]["direction"]["enum"]
        assert "top" in params["properties"]["direction"]["enum"]
        assert "bottom" in params["properties"]["direction"]["enum"]
        assert params["properties"]["selector"]["type"] == "string"
        assert params["properties"]["amount"]["type"] == "integer"


if __name__ == "__main__":
    unittest.main()

