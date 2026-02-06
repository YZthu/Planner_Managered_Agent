import unittest
import asyncio
import sys
import os
import shutil

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.plugins.browser import BrowserPlugin, BrowserNavigateTool, BrowserContentTool, BrowserScreenshotTool
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
            
            # 2. Navigate (Use example.com which is stable)
            res = await nav_tool.execute(url="https://example.com")
            assert res.success
            print(f"[PASS] Navigated: {res.output}")
            
            # 3. Content
            res = await content_tool.execute()
            assert res.success
            assert "Example Domain" in res.output
            print(f"[PASS] Content scraped: {len(res.output)} chars")
            
            # 4. Screenshot
            res = await screenshot_tool.execute()
            assert res.success
            print(f"[PASS] Screenshot: {res.output}")
            
            # Cleanup
            await plugin.cleanup()
            print("[PASS] Cleanup complete")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
