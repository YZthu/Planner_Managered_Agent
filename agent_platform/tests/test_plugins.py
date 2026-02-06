import unittest
import asyncio
import sys
import os
from unittest.mock import AsyncMock

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.plugins import plugin_registry, BasePlugin
from backend.plugins.core import CorePlugin

class TestPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "test_plugin"
    
    async def on_load(self):
        self.loaded = True

class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # Reset registry for each test if possible, or just rely on overwriting
        
    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_registry(self):
        async def run_test():
            print("Testing Plugin Registry...")
            
            # 1. Register Core Plugin
            core = CorePlugin()
            plugin_registry.register_plugin(core)
            assert plugin_registry.get_plugin("core") is not None
            print("[PASS] Core Plugin registered")
            
            # 2. Initialize
            await plugin_registry.initialize()
            print("[PASS] Registry initialized")
            
            # 3. Check Tools
            tools = plugin_registry.get_all_tools()
            tool_names = [t.name for t in tools]
            assert "web_search" in tool_names
            assert "spawn_subagent" in tool_names
            print(f"[PASS] Tools loaded: {tool_names}")
            
            # 4. Custom Plugin
            custom = TestPlugin()
            plugin_registry.register_plugin(custom)
            await plugin_registry.initialize() # Should call on_load
            assert getattr(custom, 'loaded', False) is True
            print("[PASS] Custom plugin loaded and initialized")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
