import sys
import os
import asyncio
import time
from unittest.mock import AsyncMock

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.config import config
from backend.core.session import SessionManager

async def test_debouncing():
    print("Testing Message Debouncing...")
    
    # 1. Setup
    config.agent.debounce_ms = 500  # 500ms window
    manager = SessionManager()
    session_id = "test_debounce"
    
    # Mock the agent run method to track calls
    session = manager.get_session(session_id)
    session.agent.run = AsyncMock(return_value="Mocked Response")
    
    # 2. Simulate rapid requests
    print("   Sending 3 messages rapidly...")
    start_time = time.time()
    
    results = await asyncio.gather(
        manager.handle_message(session_id, "Message 1"),
        manager.handle_message(session_id, "Message 2"),
        manager.handle_message(session_id, "Message 3")
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 3. Validation
    # All requests should return the same response
    assert all(r == "Mocked Response" for r in results), "Not all requests returned mocked response"
    print("   [PASS] All requests successfully awaited")
    
    # Agent should only be called ONCE
    call_count = session.agent.run.call_count
    if call_count == 1:
        print("   [PASS] Agent called exactly ONCE")
    else:
        print(f"   [FAIL] Agent called {call_count} times (expected 1)")
        
    # Check arguments: should contain combined text
    args = session.agent.run.call_args[0][0]
    if "Message 1" in args and "Message 2" in args and "Message 3" in args:
        print(f"   [PASS] Messages combined: {args!r}")
    else:
        print(f"   [FAIL] Messages NOT combined properly: {args!r}")

    # Check timing: should wait at least debounce_ms
    if duration >= 0.5:
        print(f"   [PASS] Debounce duration respected ({duration:.2f}s >= 0.5s)")
    else:
        print(f"   [WARN] Debounce too fast ({duration:.2f}s) - might be flaky")

async def main():
    await test_debouncing()

if __name__ == "__main__":
    asyncio.run(main())
