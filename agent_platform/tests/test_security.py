import unittest
import asyncio
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.security.access_control import AccessControl, access_control
from backend.core.agent import AgentExecutor
from backend.config import config, RoleConfig, SecurityConfig
from backend.tools.base import BaseTool, ToolResult

# Mock Tool
class MockDangerousTool(BaseTool):
    @property
    def name(self): return "nuclear_launch"
    @property
    def description(self): return "Big boom"
    @property
    def parameters(self): return {}
    async def execute(self, **kwargs): return ToolResult(success=True, output="BOOM")

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Configure Security
        config.security = SecurityConfig(
            enabled=True,
            default_role="user",
            roles={
                "admin": RoleConfig(allow=["*"]),
                "guest": RoleConfig(allow=["safe_tool"], deny=["nuclear_*"]),
                "restricted": RoleConfig(allow=["*"], deny=["nuclear_launch"])
            }
        )
        
        # Re-init access control to pick up new config
        self.ac = AccessControl() # Local instance for first test
        # Reload global instance for AgentExecutor test
        access_control.reload_config()

    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_permission_logic(self):
        print("Testing Permission Logic...")
        
        # Admin
        assert self.ac.check_permission("admin", "any_tool") == True
        print("[PASS] Admin allowed all")
        
        # Guest
        assert self.ac.check_permission("guest", "safe_tool") == True
        assert self.ac.check_permission("guest", "nuclear_launch") == False  # Deny wildcard
        assert self.ac.check_permission("guest", "other_tool") == False # Not in allow
        print("[PASS] Guest restrictions verified")
        
        # Restricted (Allow all but one)
        assert self.ac.check_permission("restricted", "safe_tool") == True
        assert self.ac.check_permission("restricted", "nuclear_launch") == False # Specific deny override
        print("[PASS] Restricted role verified")

    def test_agent_enforcement(self):
        async def run_test():
            print("Testing Agent Enforcement...")
            
            tool = MockDangerousTool()
            
            # 1. Guest Agent
            agent_guest = AgentExecutor(tools=[tool], role="guest")
            res = await agent_guest._execute_tool("nuclear_launch", {})
            assert res.success == False
            assert "Permission Denied" in res.output
            print(f"[PASS] Guest blocked: {res.output}")
            
            # 2. Admin Agent
            agent_admin = AgentExecutor(tools=[tool], role="admin")
            res = await agent_admin._execute_tool("nuclear_launch", {})
            assert res.success == True
            assert "BOOM" in res.output
            print(f"[PASS] Admin allowed: {res.output}")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
