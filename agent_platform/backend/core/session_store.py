"""
Session Store
JSON-based persistence for conversation sessions.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class SessionMessage:
    """Represents a message in a session."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMessage":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionEntry:
    """Represents a conversation session."""
    session_id: str
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    display_name: Optional[str] = None
    agent_id: Optional[str] = None
    persona: Optional[str] = None
    model_provider: Optional[str] = None
    model: Optional[str] = None
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Conversation summary (for compaction)
    summary: Optional[str] = None
    
    # Messages stored separately for efficiency
    message_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionStore:
    """JSON-based session persistence."""
    
    def __init__(self, store_path: str = "./data/sessions"):
        self.store_path = Path(store_path)
        self._sessions: Dict[str, SessionEntry] = {}
        self._loaded = False
        self._index_file = self.store_path / "index.json"
    
    def _ensure_dir(self) -> None:
        """Ensure store directory exists."""
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def _session_file(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.store_path / f"{session_id}.json"
    
    def _load_index(self) -> None:
        """Load session index from disk."""
        if not self._index_file.exists():
            self._sessions = {}
            return
        
        try:
            with open(self._index_file, 'r') as f:
                data = json.load(f)
            
            self._sessions = {}
            for session_id, entry_data in data.get("sessions", {}).items():
                self._sessions[session_id] = SessionEntry.from_dict(entry_data)
            
            logger.debug(f"Loaded index with {len(self._sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Failed to load session index: {e}")
            self._sessions = {}
    
    def _save_index(self) -> None:
        """Save session index to disk."""
        self._ensure_dir()
        
        index_data = {
            "version": 1,
            "sessions": {
                session_id: entry.to_dict()
                for session_id, entry in self._sessions.items()
            }
        }
        
        tmp_path = self._index_file.with_suffix(f".{os.getpid()}.tmp")
        
        try:
            with open(tmp_path, 'w') as f:
                json.dump(index_data, f, indent=2)
            tmp_path.rename(self._index_file)
        except Exception as e:
            logger.error(f"Failed to save session index: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    def _ensure_loaded(self) -> None:
        """Ensure index is loaded."""
        if not self._loaded:
            self._load_index()
            self._loaded = True
    
    def create_session(
        self,
        session_id: str,
        display_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        persona: Optional[str] = None,
        model_provider: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionEntry:
        """Create a new session."""
        self._ensure_loaded()
        
        entry = SessionEntry(
            session_id=session_id,
            display_name=display_name,
            agent_id=agent_id,
            persona=persona,
            model_provider=model_provider,
            model=model,
            metadata=metadata or {}
        )
        
        self._sessions[session_id] = entry
        self._save_index()
        
        # Create empty messages file
        self._save_messages(session_id, [])
        
        logger.info(f"Created session: {session_id}")
        return entry
    
    def get_session(self, session_id: str) -> Optional[SessionEntry]:
        """Get a session by ID."""
        self._ensure_loaded()
        return self._sessions.get(session_id)
    
    def update_session(self, entry: SessionEntry) -> None:
        """Update a session entry."""
        self._ensure_loaded()
        entry.updated_at = datetime.now().timestamp()
        self._sessions[entry.session_id] = entry
        self._save_index()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        self._ensure_loaded()
        
        if session_id not in self._sessions:
            return False
        
        # Delete messages file
        msg_file = self._session_file(session_id)
        if msg_file.exists():
            msg_file.unlink()
        
        # Remove from index
        del self._sessions[session_id]
        self._save_index()
        
        logger.info(f"Deleted session: {session_id}")
        return True
    
    def list_sessions(self, limit: Optional[int] = None) -> List[SessionEntry]:
        """List all sessions, sorted by updated_at descending."""
        self._ensure_loaded()
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )
        if limit:
            sessions = sessions[:limit]
        return sessions
    
    def _save_messages(self, session_id: str, messages: List[SessionMessage]) -> None:
        """Save messages for a session."""
        self._ensure_dir()
        
        msg_file = self._session_file(session_id)
        msg_data = {
            "version": 1,
            "session_id": session_id,
            "messages": [msg.to_dict() for msg in messages]
        }
        
        tmp_path = msg_file.with_suffix(f".{os.getpid()}.tmp")
        
        try:
            with open(tmp_path, 'w') as f:
                json.dump(msg_data, f, indent=2)
            tmp_path.rename(msg_file)
        except Exception as e:
            logger.error(f"Failed to save messages for session {session_id}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    def load_messages(self, session_id: str) -> List[SessionMessage]:
        """Load messages for a session."""
        msg_file = self._session_file(session_id)
        
        if not msg_file.exists():
            return []
        
        try:
            with open(msg_file, 'r') as f:
                data = json.load(f)
            
            return [
                SessionMessage.from_dict(msg_data)
                for msg_data in data.get("messages", [])
            ]
        except Exception as e:
            logger.error(f"Failed to load messages for session {session_id}: {e}")
            return []
    
    def save_messages(
        self,
        session_id: str,
        messages: List[SessionMessage],
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """Save messages and update session metadata."""
        self._ensure_loaded()
        
        entry = self._sessions.get(session_id)
        if not entry:
            # Create session if it doesn't exist
            entry = self.create_session(session_id)
        
        # Update token counts
        entry.input_tokens += input_tokens
        entry.output_tokens += output_tokens
        entry.total_tokens = entry.input_tokens + entry.output_tokens
        entry.message_count = len(messages)
        entry.updated_at = datetime.now().timestamp()
        
        # Save messages
        self._save_messages(session_id, messages)
        self._save_index()
    
    def append_message(
        self,
        session_id: str,
        message: SessionMessage,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """Append a single message to a session."""
        messages = self.load_messages(session_id)
        messages.append(message)
        self.save_messages(session_id, messages, input_tokens, output_tokens)
    
    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[SessionMessage]:
        """Get the most recent messages from a session."""
        messages = self.load_messages(session_id)
        return messages[-limit:] if limit else messages
