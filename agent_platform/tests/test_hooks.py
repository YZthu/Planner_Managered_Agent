import unittest
import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.plugins import PluginRegistry, BasePlugin, plugin_registry

class TestHooks(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Reset registry for test
        self.registry = PluginRegistry()

    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_hook_registration_and_trigger(self):
        async def run_test():
            print("Testing Hooks System...")
            
            received_events = []
            
            # Define a handler
            async def my_handler(data):
                print(f"Hook fired with: {data}")
                received_events.append(data)
                
            # 1. Register Hook
            self.registry.register_hook("test_event", my_handler)
            
            # 2. Trigger Hook
            await self.registry.trigger_hook("test_event", data="Hello Hooks")
            
            # 3. Verify
            assert len(received_events) == 1
            assert received_events[0] == "Hello Hooks"
            print("[PASS] Hook triggered successfully")
            
            # 4. Plugin Declarative Registration
            class MyPlugin(BasePlugin):
                @property
                def name(self): return "hook_test_plugin"
                
                @property
                def hooks(self):
                    return {
                        "plugin_event": self.on_plugin_event
                    }
                
                async def on_plugin_event(self, msg):
                    received_events.append(f"Plugin: {msg}")
            
            plugin = MyPlugin()
            self.registry.register_plugin(plugin)
            await self.registry.initialize()
            
            await self.registry.trigger_hook("plugin_event", msg="Native Support")
            
            assert len(received_events) == 2
            assert received_events[1] == "Plugin: Native Support"
            print("[PASS] Plugin declarative hook registered")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
