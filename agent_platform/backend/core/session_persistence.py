"""
Session Persistence
Extends the existing session management with persistent storage.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from .session_store import SessionStore, SessionEntry, SessionMessage

logger = logging.getLogger(__name__)


class PersistentSessionManager:
    """
    Session persistence manager.
    
    Works alongside the existing SessionManager/DebounceSession
    to provide persistent storage for conversation history.
    """
    
    def __init__(self, store: Optional[SessionStore] = None):
        """
        Initialize the persistence manager.
        
        Args:
            store: SessionStore instance. If None, uses default path.
        """
        self.store = store or SessionStore()
        self._active_sessions: Dict[str, List[Dict[str, Any]]] = {}
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        display_name: Optional[str] = None,
        persona: Optional[str] = None,
        model_provider: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new persistent session.
        
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        self.store.create_session(
            session_id=session_id,
            display_name=display_name,
            persona=persona,
            model_provider=model_provider,
            model=model,
            metadata=metadata
        )
        
        self._active_sessions[session_id] = []
        logger.info(f"Created persistent session: {session_id}")
        return session_id
    
    def load_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load conversation history for a session.
        
        Returns:
            List of message dicts with 'role' and 'content'
        """
        # Check cache first
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        
        # Load from store
        messages = self.store.load_messages(session_id)
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        self._active_sessions[session_id] = history
        return history
    
    def save_history(
        self,
        session_id: str,
        history: List[Dict[str, Any]],
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """
        Save conversation history for a session.
        
        Args:
            session_id: Session ID
            history: List of message dicts with 'role' and 'content'
            input_tokens: Number of input tokens used in this turn
            output_tokens: Number of output tokens generated
        """
        # Ensure session exists
        if not self.store.get_session(session_id):
            self.create_session(session_id)
        
        # Convert to SessionMessage objects
        messages = [
            SessionMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                metadata=msg.get("metadata", {})
            )
            for msg in history
        ]
        
        self.store.save_messages(session_id, messages, input_tokens, output_tokens)
        self._active_sessions[session_id] = history
    
    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """
        Append a conversation turn (user message + assistant response).
        """
        # Load existing history
        history = self.load_history(session_id)
        
        # Add new messages
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_response})
        
        # Save updated history
        self.save_history(session_id, history, input_tokens, output_tokens)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata.
        """
        entry = self.store.get_session(session_id)
        if not entry:
            return None
        
        return {
            "session_id": entry.session_id,
            "display_name": entry.display_name,
            "created_at": datetime.fromtimestamp(entry.created_at).isoformat(),
            "updated_at": datetime.fromtimestamp(entry.updated_at).isoformat(),
            "persona": entry.persona,
            "model_provider": entry.model_provider,
            "model": entry.model,
            "input_tokens": entry.input_tokens,
            "output_tokens": entry.output_tokens,
            "total_tokens": entry.total_tokens,
            "message_count": entry.message_count,
            "summary": entry.summary,
            "metadata": entry.metadata
        }
    
    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all persistent sessions.
        """
        entries = self.store.list_sessions(limit)
        return [
            {
                "session_id": e.session_id,
                "display_name": e.display_name,
                "created_at": datetime.fromtimestamp(e.created_at).isoformat(),
                "updated_at": datetime.fromtimestamp(e.updated_at).isoformat(),
                "persona": e.persona,
                "model": e.model,
                "message_count": e.message_count,
                "total_tokens": e.total_tokens
            }
            for e in entries
        ]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its history.
        """
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
        
        return self.store.delete_session(session_id)
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        """
        return self.store.get_session(session_id) is not None
    
    def update_summary(self, session_id: str, summary: str) -> None:
        """
        Update session summary (for context compaction).
        """
        entry = self.store.get_session(session_id)
        if entry:
            entry.summary = summary
            self.store.update_session(entry)
    
    def get_summary(self, session_id: str) -> Optional[str]:
        """
        Get session summary.
        """
        entry = self.store.get_session(session_id)
        return entry.summary if entry else None
    
    def get_token_usage(self, session_id: str) -> Dict[str, int]:
        """
        Get cumulative token usage for a session.
        """
        entry = self.store.get_session(session_id)
        if entry:
            return {
                "input_tokens": entry.input_tokens,
                "output_tokens": entry.output_tokens,
                "total_tokens": entry.total_tokens
            }
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


# Global persistence manager instance
_persistence_manager: Optional[PersistentSessionManager] = None


def get_persistence_manager() -> PersistentSessionManager:
    """Get the global persistence manager instance."""
    global _persistence_manager
    if _persistence_manager is None:
        from ..config import config
        session_config = getattr(config, 'session', None)
        if session_config and hasattr(session_config, 'store_path'):
            _persistence_manager = PersistentSessionManager(
                SessionStore(session_config.store_path)
            )
        else:
            _persistence_manager = PersistentSessionManager()
    return _persistence_manager
