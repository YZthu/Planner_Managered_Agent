"""
Gateway API
JSON-RPC 2.0 implementation for bi-directional agent communication.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, Awaitable, Union, List
from pydantic import BaseModel, Field, ValidationError

from .websocket import websocket_manager
from ..core.session import session_manager

logger = logging.getLogger(__name__)

# --- JSON-RPC 2.0 Models ---

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[str, int]] = None  # Notification if None

class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data

# Standard JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# --- Gateway Handler ---

class GatewayHandler:
    """
    Handles JSON-RPC messages from WebSockets.
    Dispatches methods to registered handlers.
    """
    def __init__(self):
        self._methods: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._register_default_methods()

    def register_method(self, name: str, handler: Callable[..., Awaitable[Any]]):
        """Register a new RPC method"""
        self._methods[name] = handler
        logger.info(f"Registered RPC method: {name}")

    def _register_default_methods(self):
        """Register core platform methods"""
        self.register_method("chat.send", self._handle_chat_send)
        self.register_method("session.clear", self._handle_session_clear)
        self.register_method("agent.stop", self._handle_agent_stop)
        self.register_method("system.ping", self._handle_ping)

    async def process_message(self, session_id: str, message: str) -> Optional[str]:
        """
        Process a raw WebSocket message as JSON-RPC.
        Returns a JSON string response if applicable, or None.
        """
        try:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                return self._error_response(None, PARSE_ERROR, "Parse error")

            # Handle Batch (Not implemented yet, assume single object)
            if isinstance(data, list):
                return self._error_response(None, INVALID_REQUEST, "Batch not supported yet")

            try:
                request = JsonRpcRequest(**data)
            except ValidationError:
                return self._error_response(data.get("id"), INVALID_REQUEST, "Invalid Request")

            # Check method existence
            if request.method not in self._methods:
                if request.id is not None:
                    return self._error_response(request.id, METHOD_NOT_FOUND, "Method not found")
                return None  # Ignore unknown notifications

            # Execute handler
            try:
                params = request.params or {}
                # Support both dict and list params (simplified to dict for now)
                if isinstance(params, list):
                    # Would need introspection to map list to args
                    return self._error_response(request.id, INVALID_PARAMS, "Positional params not supported yet")
                
                # Inject session_id if needed by the handler
                # We intentionally don't pass it in 'params' from client for security/consistency
                # But the handler might need it. We'll handle this by functools.partial or
                # simply passing it as a concealed kwarg if the handler accepts it.
                # For this implementation, we'll wrapper handlers to expect (session_id, params).
                
                result = await self._methods[request.method](session_id, params)
                
                if request.id is not None:
                    return JsonRpcResponse(id=request.id, result=result).model_dump_json()
                
            except JsonRpcError as e:
                return self._error_response(request.id, e.code, e.message, e.data)
            except Exception as e:
                logger.error(f"Internal RPC Error: {e}", exc_info=True)
                return self._error_response(request.id, INTERNAL_ERROR, "Internal error")

        except Exception as e:
            logger.critical(f"Critical Gateway Error: {e}", exc_info=True)
            return None # Should probably close connection

    def _error_response(self, req_id: Any, code: int, message: str, data: Any = None) -> str:
        """Helper to build error response"""
        # Spec: If id is None, it's a notification, UNLESS it's a Parse Error or Invalid Request
        if req_id is None and code not in [PARSE_ERROR, INVALID_REQUEST]:
            return None # Notifications don't get errors
            
        return JsonRpcResponse(
            id=req_id,
            error={"code": code, "message": message, "data": data}
        ).model_dump_json()

    # --- Core Method Implementations ---

    async def _handle_chat_send(self, session_id: str, params: Dict[str, Any]) -> str:
        """
        Params: { "message": "hello", "provider": "optional" }
        """
        message = params.get("message")
        if not message:
            raise JsonRpcError(INVALID_PARAMS, "Message is required")
            
        provider = params.get("provider")
        if provider:
            session = session_manager.get_session(session_id)
            try:
                session.agent.set_provider(provider)
            except Exception as e:
                raise JsonRpcError(INVALID_PARAMS, str(e))

        # This waits for the result (debounced)
        # For a truly async notification stream, we might return "accepted" 
        # and let the "agent.thought" / "agent.response" events handle the rest.
        # But JSON-RPC request/response implies a return value.
        # Let's return the final text response here to keep it simple RPC-style.
        try:
            response = await session_manager.handle_message(session_id, message)
            return response
        except Exception as e:
            raise JsonRpcError(INTERNAL_ERROR, str(e))

    async def _handle_session_clear(self, session_id: str, params: Dict[str, Any]) -> str:
        session_manager.clear_session(session_id)
        return "cleared"

    async def _handle_agent_stop(self, session_id: str, params: Dict[str, Any]) -> str:
        # Not fully implemented in agent.py yet, but placeholder
        return "stopped"

    async def _handle_ping(self, session_id: str, params: Dict[str, Any]) -> str:
        return "pong"

# Global instance
gateway = GatewayHandler()
