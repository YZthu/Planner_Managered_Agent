"""
WebSocket Manager
Handles real-time communication with frontend.
"""
import asyncio
import json
from typing import Dict, Set, Any
from fastapi import WebSocket


class WebSocketManager:
    """Manager for WebSocket connections"""
    
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str = "default"):
        """Accept and register a WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, session_id: str = "default"):
        """Remove a WebSocket connection"""
        async with self._lock:
            if session_id in self._connections:
                self._connections[session_id].discard(websocket)
                if not self._connections[session_id]:
                    del self._connections[session_id]
    
    async def send_to_session(self, session_id: str, data: Dict[str, Any]):
        """Send data to all connections for a session"""
        async with self._lock:
            connections = self._connections.get(session_id, set()).copy()
        
        message = json.dumps(data)
        disconnected = []
        
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if session_id in self._connections:
                        self._connections[session_id].discard(ws)
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast to all connections"""
        async with self._lock:
            all_connections = [
                (sid, ws) 
                for sid, conns in self._connections.items() 
                for ws in conns
            ]
        
        message = json.dumps(data)
        for session_id, websocket in all_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                pass


# Global instance
websocket_manager = WebSocketManager()
