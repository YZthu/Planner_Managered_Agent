import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.agent import AgentExecutor
from backend.core.plugins import plugin_registry
from backend.plugins.browser import BrowserPlugin, BrowserNavigateTool, BrowserContentTool
from backend.plugins.core import CorePlugin
from backend.tools.base import ToolResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deep_research():
    print("\n=== Testing Deep Research Agent ===\n")

    # 1. Initialize Plugins (required for browser tools)
    print("-> Initializing Plugins (Core & Browser)...")
    plugin_registry.register_plugin(CorePlugin())
    plugin_registry.register_plugin(BrowserPlugin())
    await plugin_registry.initialize()

    # MOCK BROWSER TOOLS to work without Playwright
    # We patch the 'execute' method of the tools in the registry
    print("-> Mocking Browser Tools for test environment...")
    
    agent_tools = plugin_registry.get_all_tools()
    
    # Mock Navigate
    async def mock_navigate(self, url: str, **kwargs):
        return ToolResult(success=True, output=f"Navigated to: {url}")
    
    # Mock Content
    async def mock_content(self, **kwargs):
        return ToolResult(success=True, output="""
        <h1>Python 3.13 New Features</h1>
        <p>Key updates in Python 3.13 include:</p>
        <ul>
            <li>Experimental JIT Compiler</li>
            <li>Removal of the GIL (Global Interpreter Lock) in free-threaded build</li>
            <li>Improved error messages</li>
        </ul>
        <p>Release Date: October 2024</p>
        """)

    # Apply patches to the tool instances
    for tool in agent_tools:
        if isinstance(tool, BrowserNavigateTool):
            tool.execute = lambda url, **kwargs: mock_navigate(tool, url, **kwargs)
        if isinstance(tool, BrowserContentTool):
            tool.execute = lambda **kwargs: mock_content(tool, **kwargs)

    # 2. Create Agent
    print("-> Creating AgentExecutor...")
    # Pass the patched tools explicitly to the agent
    agent = AgentExecutor(session_id="test_deep_research", tools=agent_tools)
    
    # 3. Set Persona
    print("-> Setting Persona to 'deep_research'...")
    agent.set_persona("deep_research")
    
    # Verify tools are loaded
    print(f"-> Available tools: {list(agent.tools.keys())}")
    
    # 4. Run Query
    query = "What are the key new features in Python 3.13? Please check 2-3 sources and summarize."
    print(f"\n-> Running Query: '{query}'")
    print("(This may take a minute as it browses real web pages...)\n")
    
    # Define an event handler to print thoughts and tool calls
    async def on_event(event_type, data):
        if event_type == "thinking":
            print(f"\n[THOUGHT] {data.get('content') or data.get('status')}")
        elif event_type == "tool_calls":
            for tool in data.get("tools", []):
                print(f"\n[TOOL CALL] {tool['name']}({tool['args']})")
        elif event_type == "tool_result":
            result = data.get("result", "")
            print(f"[TOOL RESULT] {result[:200]}..." if len(result) > 200 else f"[TOOL RESULT] {result}")

    agent.set_event_handler(on_event)

    # Execute
    response = await agent.run(query, max_iterations=5)
    
    print("\n" + "="*50)
    print("FINAL RESPONSE:")
    print("="*50)
    print(response)
    print("="*50)

    # Cleanup
    await plugin_registry.get_plugin("browser").cleanup()

if __name__ == "__main__":
    asyncio.run(test_deep_research())
