import asyncio
import json
import unittest
import sys
import os
from unittest.mock import AsyncMock, patch

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.api.gateway import gateway
from backend.core.session import session_manager

class TestGatewayProtocol(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)

    def test_gateway_protocol(self):
        async def run_test():
            print("Testing Gateway JSON-RPC Protocol...")
            
            # 1. Invalid JSON
            resp = await gateway.process_message("test_sess", "invalid_json}")
            assert resp is not None
            data = json.loads(resp)
            assert data["error"]["code"] == -32700
            print("[PASS] Parse Error handled")

            # 2. Invalid Request (missing method)
            resp = await gateway.process_message("test_sess", json.dumps({"id": 1}))
            data = json.loads(resp)
            assert data["error"]["code"] == -32600
            print("[PASS] Invalid Request handled")

            # 3. Method Not Found
            resp = await gateway.process_message("test_sess", json.dumps({
                "jsonrpc": "2.0",
                "method": "unknown.method",
                "id": 2
            }))
            data = json.loads(resp)
            assert data["error"]["code"] == -32601
            print("[PASS] Method Not Found handled")

            # 4. Success Case (system.ping)
            resp = await gateway.process_message("test_sess", json.dumps({
                "jsonrpc": "2.0",
                "method": "system.ping",
                "id": 3
            }))
            data = json.loads(resp)
            assert data["result"] == "pong"
            assert data["id"] == 3
            print("[PASS] system.ping success")

            # 5. Chat Send (Mocked)
            with patch.object(session_manager, 'handle_message', new_callable=AsyncMock) as mock_handle:
                mock_handle.return_value = "Hello World"
                
                resp = await gateway.process_message("test_sess", json.dumps({
                    "jsonrpc": "2.0",
                    "method": "chat.send",
                    "params": {"message": "Hi"},
                    "id": 4
                }))
                
                data = json.loads(resp)
                assert data["result"] == "Hello World"
                mock_handle.assert_called_with("test_sess", "Hi")
                print("[PASS] chat.send success")

        self.run_async(run_test())

if __name__ == "__main__":
    unittest.main()
