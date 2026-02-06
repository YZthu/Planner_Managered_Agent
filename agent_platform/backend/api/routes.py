"""
API Routes
REST API endpoints for the agent platform.
"""
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .websocket import websocket_manager
from .websocket import websocket_manager
from ..core.session import session_manager
from ..core.agent import get_subagent_status
from ..core.queue import subagent_queue
from ..config import config


router = APIRouter()


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    provider: Optional[str] = None  # gemini, deepseek, or openai


class ProviderRequest(BaseModel):
    provider: str  # gemini, deepseek, or openai


class ChatResponse(BaseModel):
    response: str
    session_id: str


class StatusResponse(BaseModel):
    status: str
    active_subagents: int
    queued_subagents: int





@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get a response (debounced)"""
    try:
        # Ensure session has event handler
        session = session_manager.get_session(request.session_id)
        
        # Define handler if not valid (naive check, optimal would be to set once)
        # But AgentExecutor.set_event_handler just overwrites, so it's safe to set again
        async def event_handler(event_type: str, data: dict):
            await websocket_manager.send_to_session(request.session_id, {
                "jsonrpc": "2.0",
                "method": f"agent.{event_type}",
                "params": data
            })
        session.set_event_handler(event_handler)
        
        response = await session_manager.handle_message(request.session_id, request.message)
        return ChatResponse(
            response=response,
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/provider/{session_id}")
async def set_provider(session_id: str, request: ProviderRequest):
    """Change the LLM provider for a session"""
    valid_providers = ["gemini", "deepseek", "openai"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid provider. Choose from: {valid_providers}"
        )
    
    session = session_manager.get_session(session_id)
    session.agent.set_provider(request.provider)
    
    return {
        "status": "success",
        "session_id": session_id,
        "provider": request.provider
    }


@router.get("/status")
async def get_status():
    """Get platform status"""
    queue_status = subagent_queue.get_status()
    return StatusResponse(
        status="running",
        active_subagents=queue_status["active"],
        queued_subagents=queue_status["queued"]
    )


@router.get("/subagents/{session_id}")
async def get_subagents(session_id: str):
    """Get subagent status for a session"""
    subagents = await get_subagent_status(session_id)
    return {"subagents": subagents}


@router.post("/clear/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session"""
    session_manager.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/config")
async def get_config():
    """Get current configuration (non-sensitive)"""
    return {
        "llm": {
            "default_provider": config.llm.default_provider,
            "providers": [
                {"name": "gemini", "model": config.llm.gemini_model, "configured": bool(config.llm.google_api_key)},
                {"name": "deepseek", "model": config.llm.deepseek_model, "configured": bool(config.llm.deepseek_api_key)},
                {"name": "openai", "model": config.llm.openai_model, "configured": bool(config.llm.openai_api_key)},
            ]
        },
        "agent": {
            "max_concurrent_subagents": config.agent.max_concurrent_subagents,
            "subagent_timeout_seconds": config.agent.subagent_timeout_seconds,
        }
    }


from .gateway import gateway

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for JSON-RPC 2.0 communication"""
    await websocket_manager.connect(websocket, session_id)
    
    # Ensure registry is initialized
    await registry.initialize()
    
    # Initialize Plugins
    # Initialize Plugins based on configuration
    from ..core.plugins import plugin_registry
    from ..plugins.core import CorePlugin
    from ..plugins.memory import MemoryPlugin
    from ..plugins.browser import BrowserPlugin
    from ..plugins.network import NetworkPlugin
    
    # Map plugin names to classes
    plugin_map = {
        "core": CorePlugin,
        "memory": MemoryPlugin,
        "browser": BrowserPlugin,
        "network": NetworkPlugin
    }
    
    # Get enabled plugins from config, default to all if not specified
    enabled_plugins = getattr(config, "plugins", {}).get("enabled", list(plugin_map.keys()))
    
    for plugin_name in enabled_plugins:
        plugin_class = plugin_map.get(plugin_name)
        if plugin_class:
            plugin_registry.register_plugin(plugin_class())
        else:
            print(f"Warning: Unknown plugin '{plugin_name}' in configuration")
    
    await plugin_registry.initialize()
    
    # Register Event Handler for this session to emit JSON-RPC notifications
    session = session_manager.get_session(session_id)
    async def event_handler(event_type: str, data: dict):
        await websocket_manager.send_to_session(session_id, {
            "jsonrpc": "2.0",
            "method": f"agent.{event_type}",
            "params": data
        })
    session.set_event_handler(event_handler)
    
    # Send initial status (as a Notification)
    subagents = await get_subagent_status(session_id)
    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "agent.status",
        "params": {
            "session_id": session_id,
            "subagents": subagents
        }
    })
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            # Use Gateway to process request
            response = await gateway.process_message(session_id, data)
            
            if response:
                await websocket.send_text(response)
            
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, session_id)
