import asyncio
from typing import Dict, Optional, List
from datetime import datetime

from ..config import config
from .agent import AgentExecutor
from datetime import datetime

from ..config import config
from .agent import AgentExecutor

class DebounceSession:
    """
    Manages a single user session with message debouncing.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent = AgentExecutor(session_id=session_id)
        self.message_buffer: List[str] = []
        self._debounce_task: Optional[asyncio.Task] = None
        self._response_future: Optional[asyncio.Future] = None
        self._lock = asyncio.Lock()
        
    def set_event_handler(self, handler):
        self.agent.set_event_handler(handler)

    async def handle_message(self, message: str) -> str:
        """
        Add message to buffer and wait for debounced execution.
        Returns the final agent response.
        """
        async with self._lock:
            self.message_buffer.append(message)
            
            # If we already have a pending response future, join it
            if self._response_future and not self._response_future.done():
                pass
            else:
                self._response_future = asyncio.Future()

            # Reset debounce timer
            if self._debounce_task:
                self._debounce_task.cancel()
            
            self._debounce_task = asyncio.create_task(self._debounce_process())
            
        # Wait for the result
        return await self._response_future

    async def _debounce_process(self):
        """Wait for debounce timeout then execute"""
        try:
            # Wait for debounce window
            await asyncio.sleep(config.agent.debounce_ms / 1000.0)
            
            async with self._lock:
                # Combine messages
                if not self.message_buffer:
                    return
                
                # Simple joining strategy - can be improved with prompt engineering
                combined_message = "\n\n".join(self.message_buffer)
                self.message_buffer.clear()
                
                # Signal we are starting
                # In a real system, we might stream this, but for now we block
                
            try:
                # Run agent (outside lock to allow other operations if needed)
                response = await self.agent.run(combined_message)
                
                # Resolve all waiting requests with the same response
                if self._response_future and not self._response_future.done():
                    self._response_future.set_result(response)
                    
            except Exception as e:
                if self._response_future and not self._response_future.done():
                    self._response_future.set_exception(e)
                    
        except asyncio.CancelledError:
            # New message arrived, resetting timer
            pass


class SessionManager:
    """Global manager for active sessions"""
    def __init__(self):
        self._sessions: Dict[str, DebounceSession] = {}

    def get_session(self, session_id: str) -> DebounceSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = DebounceSession(session_id)
        return self._sessions[session_id]

    async def handle_message(self, session_id: str, message: str) -> str:
        session = self.get_session(session_id)
        return await session.handle_message(message)

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].agent.clear_history()

# Global instance
session_manager = SessionManager()
