"""
Manual Verification Script: Deep Research Persona
Verifies browser navigation and content extraction.
"""
import asyncio
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.agent import AgentExecutor
from backend.core.startup import initialize_plugins

async def verify_deep_research():
    print("🚀 Initializing plugins...")
    await initialize_plugins()
    
    print("🎭 Setting up Deep Research agent...")
    agent = AgentExecutor()
    success = agent.set_persona("deep_research")
    
    if not success:
        print("❌ Failed to set deep_research persona (likely missing browser tools)")
        return
    
    print("✅ Deep Research persona active!")
    
    # Test browser_navigate if possible
    browser_tools = [t for t in agent.tools.values() if t.name.startswith("browser_")]
    if not browser_tools:
        print("❌ No browser tools found in agent!")
        return
    
    print(f"🛠 Found {len(browser_tools)} browser tools: {[t.name for t in browser_tools]}")
    
    # Actually try a simple navigation
    navigate_tool = agent.tools.get("browser_navigate")
    if navigate_tool:
        print("🌐 Testing browser_navigate (visiting example.com)...")
        try:
            result = await navigate_tool.execute(url="https://example.com")
            if result.success:
                print(f"✅ Navigation successful! Output snippet: {result.output[:100]}...")
            else:
                print(f"❌ Navigation failed: {result.output}")
        except Exception as e:
            print(f"❌ Exception during navigation: {e}")
    
    print("🏁 Verification complete.")

if __name__ == "__main__":
    asyncio.run(verify_deep_research())
