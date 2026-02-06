"""
Tests for Audit Logging
"""
import pytest
from pathlib import Path
from datetime import date, datetime, timedelta
import json


class TestAuditStore:
    """Test audit log storage."""
    
    def test_append_entry(self, tmp_path):
        """Test appending an audit entry."""
        from backend.security.audit_store import AuditStore, AuditEntry
        
        store = AuditStore(str(tmp_path / "audit"))
        
        entry = AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="tool_execution",
            severity="info",
            message="Test tool executed"
        )
        
        store.append(entry)
        
        # Verify log file exists
        log_file = tmp_path / "audit" / f"{date.today().isoformat()}.jsonl"
        assert log_file.exists()
        
        # Verify content
        with open(log_file) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["event_type"] == "tool_execution"
            assert data["message"] == "Test tool executed"
    
    def test_read_entries(self, tmp_path):
        """Test reading audit entries."""
        from backend.security.audit_store import AuditStore, AuditEntry
        
        store = AuditStore(str(tmp_path / "audit"))
        
        # Add multiple entries
        for i in range(5):
            store.append(AuditEntry(
                timestamp=datetime.now().timestamp(),
                event_type="test_event",
                severity="info",
                message=f"Entry {i}"
            ))
        
        # Read entries
        entries = store.read_entries()
        
        assert len(entries) == 5
        assert entries[0].message == "Entry 0"
        assert entries[4].message == "Entry 4"
    
    def test_read_recent(self, tmp_path):
        """Test reading recent entries."""
        from backend.security.audit_store import AuditStore, AuditEntry
        
        store = AuditStore(str(tmp_path / "audit"))
        
        # Add entries
        for i in range(10):
            store.append(AuditEntry(
                timestamp=datetime.now().timestamp(),
                event_type="test",
                severity="info",
                message=f"Entry {i}"
            ))
        
        # Read recent (limit 5)
        entries = store.read_recent(5)
        
        assert len(entries) == 5
        # Most recent first
        assert entries[0].message == "Entry 9"
    
    def test_search_by_event_type(self, tmp_path):
        """Test searching by event type."""
        from backend.security.audit_store import AuditStore, AuditEntry
        
        store = AuditStore(str(tmp_path / "audit"))
        
        store.append(AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="tool_execution",
            severity="info",
            message="Tool 1"
        ))
        store.append(AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="provider_call",
            severity="info",
            message="Provider 1"
        ))
        store.append(AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="tool_execution",
            severity="info",
            message="Tool 2"
        ))
        
        # Search for tool_execution only
        entries = store.search(event_type="tool_execution")
        
        assert len(entries) == 2
        assert all(e.event_type == "tool_execution" for e in entries)
    
    def test_search_by_severity(self, tmp_path):
        """Test searching by severity."""
        from backend.security.audit_store import AuditStore, AuditEntry
        
        store = AuditStore(str(tmp_path / "audit"))
        
        store.append(AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="test",
            severity="info",
            message="Info message"
        ))
        store.append(AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type="test",
            severity="warning",
            message="Warning message"
        ))
        
        entries = store.search(severity="warning")
        
        assert len(entries) == 1
        assert entries[0].severity == "warning"


class TestAuditLogger:
    """Test the audit logger."""
    
    def test_log_event(self, tmp_path):
        """Test logging a generic event."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_event(
            event_type="test_event",
            severity="info",
            message="Test message",
            session_id="session-123"
        )
        
        entries = logger.get_recent_events(1)
        assert len(entries) == 1
        assert entries[0].event_type == "test_event"
        assert entries[0].session_id == "session-123"
    
    def test_log_tool_execution(self, tmp_path):
        """Test logging tool execution."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_tool_execution(
            tool_name="web_search",
            args={"query": "test query"},
            result="Search completed",
            success=True,
            execution_time_ms=150.5
        )
        
        entries = logger.get_recent_events(1)
        assert len(entries) == 1
        assert entries[0].event_type == "tool_execution"
        assert "web_search" in entries[0].message
    
    def test_log_tool_error(self, tmp_path):
        """Test logging tool error."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_tool_execution(
            tool_name="file_write",
            args={"path": "/test/file.txt"},
            result=None,
            success=False
        )
        
        entries = logger.get_recent_events(1)
        assert entries[0].event_type == "tool_error"
        assert entries[0].severity == "warning"
    
    def test_log_provider_call(self, tmp_path):
        """Test logging provider calls."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_provider_call(
            provider="gemini",
            model="gemini-2.0-flash",
            input_tokens=100,
            output_tokens=50,
            success=True,
            latency_ms=500.0
        )
        
        entries = logger.get_recent_events(1)
        assert entries[0].event_type == "provider_call"
        assert entries[0].details["input_tokens"] == 100
        assert entries[0].details["output_tokens"] == 50
    
    def test_log_access_denied(self, tmp_path):
        """Test logging access denied events."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_access_denied(
            resource="shell_execute",
            action="execute",
            reason="Role 'user' not allowed",
            user_id="user-123"
        )
        
        entries = logger.get_recent_events(1)
        assert entries[0].event_type == "access_denied"
        assert entries[0].severity == "critical"
    
    def test_sanitize_sensitive_data(self, tmp_path):
        """Test that sensitive data is sanitized."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(store=AuditStore(str(tmp_path / "audit")))
        
        logger.log_tool_execution(
            tool_name="api_call",
            args={
                "url": "https://api.example.com",
                "api_key": "secret-key-12345",
                "password": "my-password"
            },
            result="Success",
            success=True
        )
        
        entries = logger.get_recent_events(1)
        details = entries[0].details
        
        # Sensitive fields should be redacted
        assert details["args"]["api_key"] == "[REDACTED]"
        assert details["args"]["password"] == "[REDACTED]"
        # Non-sensitive should be preserved
        assert details["args"]["url"] == "https://api.example.com"
    
    def test_logger_disabled(self, tmp_path):
        """Test that disabled logger doesn't log."""
        from backend.security.audit import AuditLogger
        from backend.security.audit_store import AuditStore
        
        logger = AuditLogger(
            store=AuditStore(str(tmp_path / "audit")),
            enabled=False
        )
        
        logger.log_event(
            event_type="test",
            severity="info",
            message="This should not be logged"
        )
        
        entries = logger.get_recent_events(10)
        assert len(entries) == 0
