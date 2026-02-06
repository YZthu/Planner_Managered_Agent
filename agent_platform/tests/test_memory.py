import unittest
import asyncio
import sys
import os
import shutil

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.plugins.memory import MemoryPlugin, AddMemoryTool, QueryMemoryTool
from backend.config import config

class TestMemoryPlugin(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Use a temporary test directory
        self.test_dir = "./data/test_memory"
        # Mock config if possible, or just rely on the plugin using the passed path in a real scenario
        # Ideally we'd patch config, but let's just clean up after
        
        # Force config update for test
        class MockMemoryConfig:
            enabled = True
            collection_name = "test_memory"
            persist_directory = "./data/test_memory"
        
        config.memory = MockMemoryConfig()

    def tearDown(self):
        self.loop.close()
        # Clean up test data
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_memory_lifecycle(self):
        async def run_test():
            print("Testing Memory Plugin...")
            
            # 1. Initialize
            plugin = MemoryPlugin()
            await plugin.on_load()
            
            tools = plugin.get_tools()
            add_tool = next(t for t in tools if t.name == "add_memory")
            query_tool = next(t for t in tools if t.name == "query_memory")
            
            if not plugin.collection:
                print("[SKIP] ChromaDB not available")
                return

            print("[PASS] Plugin initialized")
            
            # 2. Add Memory
            res = await add_tool.execute(
                text="The user's name is Alice.",
                metadata={"topic": "user_info"}
            )
            assert res.success
            print(f"[PASS] Added memory: {res.output}")
            
            res = await add_tool.execute(
                text="The user likes coding in Python.",
                metadata={"topic": "preferences"}
            )
            assert res.success
            
            # 3. Query Memory
            # Note: Chroma might take a moment to index, but usually immediate for small data
            res = await query_tool.execute(query="What is the user's name?")
            assert res.success
            assert "Alice" in res.output
            print(f"[PASS] Query 1 result: {res.output.strip()}")

            res = await query_tool.execute(query="programming language")
            assert "Python" in res.output
            print(f"[PASS] Query 2 result: {res.output.strip()}")
            
            # 4. Persistence Test (Simulate restart)
            # Create new plugin instance
            new_plugin = MemoryPlugin()
            await new_plugin.on_load()
            new_query_tool = next(t for t in new_plugin.get_tools() if t.name == "query_memory")
            
            res = await new_query_tool.execute(query="What does the user like?")
            assert "Python" in res.output
            print(f"[PASS] Persistence verified: {res.output.strip()}")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
