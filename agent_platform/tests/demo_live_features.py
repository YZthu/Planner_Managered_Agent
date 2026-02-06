import sys
import os
import asyncio
import logging

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.config import config
from backend.core.agent import AgentExecutor
from backend.tools.base import BaseTool, ToolResult
from backend.providers.base import Message, Role

# Configure logging to see internally what's happening
logging.basicConfig(level=logging.WARN)

class SleepTool(BaseTool):
    name = "sleep_tool"
    description = "Sleeps for a specified number of seconds. Useful for testing timeouts."
    parameters = {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Seconds to sleep"}
        },
        "required": ["seconds"]
    }

    async def execute(self, seconds: int, **kwargs) -> ToolResult:
        print(f"    [SleepTool] Sleeping for {seconds} seconds...")
        await asyncio.sleep(seconds)
        return ToolResult(success=True, output=f"Slept for {seconds} seconds")

async def on_agent_event(event_type: str, data: any):
    if event_type == "thinking":
        content = data.get("content", data.get("status", ""))
        print(f"🧠 [THINKING] {content}")
    elif event_type == "tool_calls":
        print(f"🛠️ [TOOL CALL] {data}")
    elif event_type == "tool_result":
        print(f"✅ [TOOL RESULT] {data}")
    elif event_type == "complete":
        print(f"🤖 [COMPLETE] Response length: {len(data.get('response', ''))}")

async def main():
    print("="*50)
    print("LIVE FEATURE DEMO")
    print("="*50)

    # 1. Test Context Window logic (local)
    print("\n1. Testing Context Window (Local Logic)...")
    agent = AgentExecutor(session_id="demo_test")
    
    # Fill with 30 messages
    print(f"   Injecting 30 dummy messages...")
    for i in range(30):
        agent._message_history.append(Message(role=Role.USER, content=f"Msg {i}"))
    
    print(f"   Current history size: {len(agent._message_history)}")
    
    # Run a simple query - this triggers the truncation logic in `run`
    # We mock the provider for this specific check to avoid API cost/latency just for history check
    # But wait, to check the logic inside `run`, we effectively need to call `run`.
    # Let's just check the state after a run invocation attempt (or just trust the previous unit test).
    # actually, let's trust the unit test for logic and focus this script on "Thinking" and "Timeout".
    
    # Reset agent for live test
    agent = AgentExecutor(session_id="demo_live")
    agent.set_event_handler(on_agent_event)
    
    # 2. Test Thinking (Live)
    print("\n2. Testing Thinking (Live API)...")
    print("   Sending complex math query...")
    response = await agent.run("Calculate 25 * 48, then explain if it is a prime number. Use <thought> tags to explain your reasoning before answering.")
    print(f"\n   Final Answer: {response[:100]}...")

    # 3. Test Tool Timeout
    print("\n3. Testing Tool Timeout...")
    # Create agent with SleepTool
    sleep_tool = SleepTool()
    agent_tools = AgentExecutor(tools=[sleep_tool], session_id="demo_timeout")
    agent_tools.set_event_handler(on_agent_event)
    
    # Temporarily lower timeout for this test
    original_timeout = config.agent.subagent_timeout_seconds
    config.agent.subagent_timeout_seconds = 2
    print(f"   Set timeout to 2 seconds.")
    
    print("   Requesting 5 second sleep...")
    try:
        # We manually construct a message history that forces tool use? 
        # Or just ask it.
        await agent_tools.run("Use the sleep_tool to sleep for 5 seconds.")
    except Exception as e:
        print(f"   [Exception] {e}")
        
    config.agent.subagent_timeout_seconds = original_timeout
    print("   Finished timeout test.")

if __name__ == "__main__":
    asyncio.run(main())
