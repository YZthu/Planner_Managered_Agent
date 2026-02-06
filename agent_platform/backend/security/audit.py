"""
Audit Logger
Security and activity logging for the agent platform.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from .audit_store import AuditStore, AuditEntry

logger = logging.getLogger(__name__)


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Tool events
    TOOL_EXECUTION = "tool_execution"
    TOOL_ERROR = "tool_error"
    
    # Provider events
    PROVIDER_CALL = "provider_call"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_FALLBACK = "provider_fallback"
    
    # Session events
    SESSION_CREATE = "session_create"
    SESSION_LOAD = "session_load"
    SESSION_SAVE = "session_save"
    SESSION_DELETE = "session_delete"
    
    # Security events
    ACCESS_DENIED = "access_denied"
    RATE_LIMIT = "rate_limit"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Agent events
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    
    # Cron events
    CRON_JOB_CREATE = "cron_job_create"
    CRON_JOB_EXECUTE = "cron_job_execute"
    CRON_JOB_DELETE = "cron_job_delete"


class AuditLogger:
    """
    Centralized audit logging for the agent platform.
    
    Logs security events, tool executions, provider calls, and more.
    """
    
    def __init__(
        self,
        store: Optional[AuditStore] = None,
        enabled: bool = True,
        log_tool_calls: bool = True,
        log_provider_calls: bool = True
    ):
        self.store = store or AuditStore()
        self.enabled = enabled
        self.log_tool_calls = log_tool_calls
        self.log_provider_calls = log_provider_calls
    
    def log_event(
        self,
        event_type: str,
        severity: str = "info",
        message: str = "",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (use AuditEventType values)
            severity: Severity level (use AuditSeverity values)
            message: Human-readable message
            session_id: Optional session ID
            user_id: Optional user ID
            details: Optional additional details
        """
        if not self.enabled:
            return
        
        entry = AuditEntry(
            timestamp=datetime.now().timestamp(),
            event_type=event_type,
            severity=severity,
            message=message,
            session_id=session_id,
            user_id=user_id,
            details=details
        )
        
        self.store.append(entry)
        
        # Also log to standard logger
        log_msg = f"[AUDIT] {event_type}: {message}"
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
    
    def log_tool_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        success: bool,
        session_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None
    ) -> None:
        """Log a tool execution."""
        if not self.enabled or not self.log_tool_calls:
            return
        
        event_type = AuditEventType.TOOL_EXECUTION if success else AuditEventType.TOOL_ERROR
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        
        # Sanitize args (remove sensitive data)
        safe_args = self._sanitize_dict(args)
        
        self.log_event(
            event_type=event_type.value,
            severity=severity.value,
            message=f"Tool '{tool_name}' {'succeeded' if success else 'failed'}",
            session_id=session_id,
            details={
                "tool_name": tool_name,
                "args": safe_args,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "result_preview": str(result)[:200] if result else None
            }
        )
    
    def log_provider_call(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        session_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Log a provider/LLM call."""
        if not self.enabled or not self.log_provider_calls:
            return
        
        event_type = AuditEventType.PROVIDER_CALL if success else AuditEventType.PROVIDER_ERROR
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        
        self.log_event(
            event_type=event_type.value,
            severity=severity.value,
            message=f"Provider '{provider}' call {'succeeded' if success else 'failed'}",
            session_id=session_id,
            details={
                "provider": provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "success": success,
                "latency_ms": latency_ms,
                "error": error
            }
        )
    
    def log_provider_fallback(
        self,
        from_provider: str,
        to_provider: str,
        reason: str,
        session_id: Optional[str] = None
    ) -> None:
        """Log a provider fallback event."""
        if not self.enabled:
            return
        
        self.log_event(
            event_type=AuditEventType.PROVIDER_FALLBACK.value,
            severity=AuditSeverity.WARNING.value,
            message=f"Fallback from '{from_provider}' to '{to_provider}'",
            session_id=session_id,
            details={
                "from_provider": from_provider,
                "to_provider": to_provider,
                "reason": reason
            }
        )
    
    def log_session_event(
        self,
        event: str,
        session_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a session lifecycle event."""
        if not self.enabled:
            return
        
        event_types = {
            "create": AuditEventType.SESSION_CREATE,
            "load": AuditEventType.SESSION_LOAD,
            "save": AuditEventType.SESSION_SAVE,
            "delete": AuditEventType.SESSION_DELETE,
        }
        
        event_type = event_types.get(event, AuditEventType.SESSION_LOAD)
        
        self.log_event(
            event_type=event_type.value,
            severity=AuditSeverity.INFO.value,
            message=f"Session {event}",
            session_id=session_id,
            details=details
        )
    
    def log_access_denied(
        self,
        resource: str,
        action: str,
        reason: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """Log an access denied event."""
        if not self.enabled:
            return
        
        self.log_event(
            event_type=AuditEventType.ACCESS_DENIED.value,
            severity=AuditSeverity.CRITICAL.value,
            message=f"Access denied to '{resource}' for action '{action}'",
            session_id=session_id,
            user_id=user_id,
            details={
                "resource": resource,
                "action": action,
                "reason": reason
            }
        )
    
    def log_agent_lifecycle(
        self,
        event: str,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log agent lifecycle events."""
        if not self.enabled:
            return
        
        event_types = {
            "start": (AuditEventType.AGENT_START, AuditSeverity.INFO),
            "complete": (AuditEventType.AGENT_COMPLETE, AuditSeverity.INFO),
            "error": (AuditEventType.AGENT_ERROR, AuditSeverity.WARNING),
        }
        
        event_type, severity = event_types.get(
            event, 
            (AuditEventType.AGENT_START, AuditSeverity.INFO)
        )
        
        self.log_event(
            event_type=event_type.value,
            severity=severity.value,
            message=f"Agent {event}",
            session_id=session_id,
            details=details
        )
    
    def get_recent_events(self, count: int = 100) -> List[AuditEntry]:
        """Get recent audit events."""
        return self.store.read_recent(count)
    
    def search_events(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Search audit events."""
        return self.store.search(
            event_type=event_type,
            severity=severity,
            session_id=session_id,
            limit=limit
        )
    
    def _sanitize_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from a dictionary."""
        sensitive_keys = {
            "password", "api_key", "apikey", "secret", "token",
            "auth", "credential", "key", "private"
        }
        
        result = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif isinstance(value, str) and len(value) > 500:
                result[key] = value[:500] + "..."
            else:
                result[key] = value
        
        return result


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        from ..config import config
        audit_config = getattr(config, 'audit', None)
        if audit_config:
            _audit_logger = AuditLogger(
                store=AuditStore(getattr(audit_config, 'store_path', './data/audit')),
                enabled=getattr(audit_config, 'enabled', True),
                log_tool_calls=getattr(audit_config, 'log_tool_calls', True),
                log_provider_calls=getattr(audit_config, 'log_provider_calls', True)
            )
        else:
            _audit_logger = AuditLogger()
    return _audit_logger
