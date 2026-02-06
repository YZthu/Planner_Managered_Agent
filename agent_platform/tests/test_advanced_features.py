import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.agent import AgentExecutor
from backend.providers.base import LLMResponse, Message, Role
from backend.tools.base import BaseTool, ToolResult
from backend.config import config

class MockProvider(AsyncMock):
    async def generate(self, messages, tools=None, **kwargs):
        # Check context window
        if len(messages) > config.agent.max_history_messages + 2: # +2 for system + new user msg
             print(f"[FAIL] Context window exceeded: {len(messages)} messages")
        
        last_msg = messages[-1].content
        if "thought" in last_msg:
             return LLMResponse(content="<thought>I am thinking...</thought>Here is the answer.")
        
        return LLMResponse(content="Response")

class SlowTool(BaseTool):
    @property
    def name(self): return "slow_tool"
    @property
    def description(self): return "A slow tool"
    @property
    def parameters(self): return {"type": "object", "properties": {}}
    
    async def execute(self, **kwargs):
        await asyncio.sleep(2) # Longer than timeout
        return ToolResult(success=True, output="Finished")

async def test_context_window():
    print("\nTesting Context Window...")
    agent = AgentExecutor(provider=MockProvider())
    
    # Fill history
    for i in range(30):
        agent._message_history.append(Message(role=Role.USER, content=f"Msg {i}"))
        
    # Run
    await agent.run("New message")
    
    # Check history size
    assert len(agent._message_history) <= config.agent.max_history_messages + 1, "History not truncated"
    print("[PASS] Context window verified")

async def test_thinking():
    print("\nTesting Thinking...")
    agent = AgentExecutor(provider=MockProvider())
    
    events = []
    agent.set_event_handler(lambda t, d: events.append((t, d)))
    
    await agent.run("Generate a thought")
    
    thought_events = [e for e in events if e[0] == "thinking" and "content" in e[1]]
    if thought_events:
        print(f"[PASS] Thinking event detected: {thought_events[0][1]['content']}")
    else:
        print("[FAIL] No thinking event detected")

async def test_tool_timeout():
    print("\nTesting Tool Timeout...")
    # Reduce timeout for test
    config.agent.subagent_timeout_seconds = 1
    
    tool = SlowTool()
    agent = AgentExecutor(tools=[tool], provider=MockProvider())
    
    result = await agent._execute_tool("slow_tool", {})
    if "timed out" in result.output:
        print("[PASS] Tool timeout verified")
    else:
        print(f"[FAIL] Tool did not timeout: {result.output}")

async def main():
    await test_context_window()
    await test_thinking()
    await test_tool_timeout()

if __name__ == "__main__":
    asyncio.run(main())
