"""
Tests for Session Persistence
"""
import pytest
from pathlib import Path
from datetime import datetime
import json


class TestSessionStore:
    """Test session storage."""
    
    def test_create_session(self, tmp_path):
        """Test creating a session."""
        from backend.core.session_store import SessionStore
        
        store = SessionStore(str(tmp_path / "sessions"))
        
        entry = store.create_session(
            session_id="test-session-1",
            display_name="Test Session",
            persona="default"
        )
        
        assert entry is not None
        assert entry.session_id == "test-session-1"
        assert entry.display_name == "Test Session"
        assert entry.persona == "default"
        assert entry.created_at > 0
    
    def test_session_save_load_messages(self, tmp_path):
        """Test saving and loading messages."""
        from backend.core.session_store import SessionStore, SessionMessage
        
        store = SessionStore(str(tmp_path / "sessions"))
        
        # Create session
        store.create_session(session_id="msg-test")
        
        # Save messages
        messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi there!"),
            SessionMessage(role="user", content="How are you?"),
        ]
        
        store.save_messages("msg-test", messages, input_tokens=50, output_tokens=30)
        
        # Load messages
        loaded = store.load_messages("msg-test")
        
        assert len(loaded) == 3
        assert loaded[0].role == "user"
        assert loaded[0].content == "Hello"
        assert loaded[1].role == "assistant"
        assert loaded[2].content == "How are you?"
    
    def test_session_token_tracking(self, tmp_path):
        """Test token usage tracking."""
        from backend.core.session_store import SessionStore, SessionMessage
        
        store = SessionStore(str(tmp_path / "sessions"))
        
        # Create session
        store.create_session(session_id="token-test")
        
        # Save messages with tokens
        messages = [SessionMessage(role="user", content="Test")]
        store.save_messages("token-test", messages, input_tokens=100, output_tokens=50)
        
        # Check token counts
        entry = store.get_session("token-test")
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.total_tokens == 150
        
        # Add more tokens
        messages.append(SessionMessage(role="assistant", content="Response"))
        store.save_messages("token-test", messages, input_tokens=50, output_tokens=100)
        
        entry = store.get_session("token-test")
        assert entry.input_tokens == 150
        assert entry.output_tokens == 150
        assert entry.total_tokens == 300
    
    def test_session_list(self, tmp_path):
        """Test listing sessions."""
        from backend.core.session_store import SessionStore
        import time
        
        store = SessionStore(str(tmp_path / "sessions"))
        
        # Create multiple sessions
        store.create_session(session_id="session-1")
        time.sleep(0.01)  # Small delay for different timestamps
        store.create_session(session_id="session-2")
        time.sleep(0.01)
        store.create_session(session_id="session-3")
        
        # List sessions (should be sorted by updated_at descending)
        sessions = store.list_sessions()
        
        assert len(sessions) == 3
        # Most recent first
        assert sessions[0].session_id == "session-3"
    
    def test_session_delete(self, tmp_path):
        """Test deleting a session."""
        from backend.core.session_store import SessionStore, SessionMessage
        
        store = SessionStore(str(tmp_path / "sessions"))
        
        # Create and populate session
        store.create_session(session_id="to-delete")
        store.save_messages("to-delete", [
            SessionMessage(role="user", content="Test")
        ])
        
        # Verify exists
        assert store.get_session("to-delete") is not None
        
        # Delete
        deleted = store.delete_session("to-delete")
        assert deleted is True
        assert store.get_session("to-delete") is None
    
    def test_append_message(self, tmp_path):
        """Test appending a single message."""
        from backend.core.session_store import SessionStore, SessionMessage
        
        store = SessionStore(str(tmp_path / "sessions"))
        store.create_session(session_id="append-test")
        
        # Append messages one by one
        store.append_message(
            "append-test",
            SessionMessage(role="user", content="First message"),
            input_tokens=10
        )
        
        store.append_message(
            "append-test",
            SessionMessage(role="assistant", content="Second message"),
            output_tokens=20
        )
        
        # Verify
        messages = store.load_messages("append-test")
        assert len(messages) == 2
        
        entry = store.get_session("append-test")
        assert entry.message_count == 2


class TestPersistentSessionManager:
    """Test the persistent session manager."""
    
    def test_create_and_load(self, tmp_path):
        """Test creating and loading a session."""
        from backend.core.session_persistence import PersistentSessionManager
        from backend.core.session_store import SessionStore
        
        manager = PersistentSessionManager(SessionStore(str(tmp_path / "sessions")))
        
        # Create session
        session_id = manager.create_session(display_name="Test")
        assert session_id is not None
        
        # Load history (should be empty)
        history = manager.load_history(session_id)
        assert history == []
    
    def test_save_and_load_history(self, tmp_path):
        """Test saving and loading conversation history."""
        from backend.core.session_persistence import PersistentSessionManager
        from backend.core.session_store import SessionStore
        
        manager = PersistentSessionManager(SessionStore(str(tmp_path / "sessions")))
        
        session_id = manager.create_session()
        
        # Save history
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        manager.save_history(session_id, history.copy())
        
        # Load in new manager instance
        manager2 = PersistentSessionManager(SessionStore(str(tmp_path / "sessions")))
        loaded = manager2.load_history(session_id)
        
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Hello"
        assert loaded[1]["content"] == "Hi!"
    
    def test_append_turn(self, tmp_path):
        """Test appending a conversation turn."""
        from backend.core.session_persistence import PersistentSessionManager
        from backend.core.session_store import SessionStore
        
        manager = PersistentSessionManager(SessionStore(str(tmp_path / "sessions")))
        
        session_id = manager.create_session()
        
        manager.append_turn(session_id, "User message", "Assistant response")
        
        history = manager.load_history(session_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
