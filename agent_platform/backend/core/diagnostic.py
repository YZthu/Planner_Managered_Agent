"""
Diagnostic Logging Module

Provides:
- Session lifecycle tracking
- Request/response tracking
- Heartbeat monitoring
- Performance metrics
"""
import time
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from .logging import get_logger

log = get_logger("diagnostic")


@dataclass
class SessionState:
    """Tracks the state of an agent session."""
    session_id: str
    state: str = "idle"  # idle, processing, waiting
    last_activity: float = field(default_factory=time.time)
    queue_depth: int = 0
    total_requests: int = 0
    total_errors: int = 0
    created_at: float = field(default_factory=time.time)


class DiagnosticTracker:
    """Centralized diagnostic tracking for the agent platform."""
    
    _instance: Optional["DiagnosticTracker"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_running = False
        
        # Global stats
        self.stats = {
            "requests_received": 0,
            "requests_processed": 0,
            "requests_errors": 0,
            "last_activity": 0,
        }
        
        self._initialized = True
    
    # Session Tracking
    
    def get_session(self, session_id: str) -> SessionState:
        """Get or create session state."""
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionState(session_id=session_id)
                log.debug(f"Session created: session_id={session_id}")
            return self.sessions[session_id]
    
    def log_session_start(self, session_id: str):
        """Log session start."""
        session = self.get_session(session_id)
        session.state = "processing"
        session.last_activity = time.time()
        log.info(f"Session started: session_id={session_id}")
    
    def log_session_end(self, session_id: str, outcome: str = "completed"):
        """Log session end."""
        session = self.get_session(session_id)
        duration = time.time() - session.last_activity
        session.state = "idle"
        session.last_activity = time.time()
        log.info(f"Session ended: session_id={session_id} outcome={outcome} duration={duration:.2f}s")
    
    def log_session_state_change(
        self,
        session_id: str,
        new_state: str,
        reason: Optional[str] = None
    ):
        """Log session state change."""
        session = self.get_session(session_id)
        prev_state = session.state
        session.state = new_state
        session.last_activity = time.time()
        
        log.debug(
            f"Session state change: session_id={session_id} prev={prev_state} "
            f"new={new_state}{f' reason={reason}' if reason else ''}"
        )
    
    # Request Tracking
    
    def log_request_received(
        self,
        session_id: str,
        request_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log incoming request."""
        session = self.get_session(session_id)
        session.queue_depth += 1
        session.total_requests += 1
        self.stats["requests_received"] += 1
        self.stats["last_activity"] = time.time()
        
        log.debug(
            f"Request received: session_id={session_id} type={request_type} "
            f"queue_depth={session.queue_depth}"
        )
    
    def log_request_processed(
        self,
        session_id: str,
        request_type: str,
        duration_ms: float,
        outcome: str = "success",
        error: Optional[str] = None
    ):
        """Log processed request."""
        session = self.get_session(session_id)
        session.queue_depth = max(0, session.queue_depth - 1)
        self.stats["requests_processed"] += 1
        
        if outcome == "error":
            session.total_errors += 1
            self.stats["requests_errors"] += 1
            log.error(
                f"Request error: session_id={session_id} type={request_type} "
                f"duration={duration_ms:.0f}ms error={error}"
            )
        else:
            log.debug(
                f"Request processed: session_id={session_id} type={request_type} "
                f"duration={duration_ms:.0f}ms outcome={outcome}"
            )
    
    # Tool Execution Tracking
    
    def log_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Log tool execution."""
        self.stats["last_activity"] = time.time()
        
        if success:
            log.debug(
                f"Tool executed: session_id={session_id} tool={tool_name} "
                f"duration={duration_ms:.0f}ms success=true"
            )
        else:
            log.warning(
                f"Tool failed: session_id={session_id} tool={tool_name} "
                f"duration={duration_ms:.0f}ms error={error}"
            )
    
    # Heartbeat
    
    def start_heartbeat(self, interval: int = 30):
        """Start diagnostic heartbeat thread."""
        if self._heartbeat_running:
            return
        
        self._heartbeat_interval = interval
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        log.info(f"Diagnostic heartbeat started (interval={interval}s)")
    
    def stop_heartbeat(self):
        """Stop diagnostic heartbeat thread."""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None
        log.info("Diagnostic heartbeat stopped")
    
    def _heartbeat_loop(self):
        """Heartbeat loop that logs system stats."""
        while self._heartbeat_running:
            try:
                self._emit_heartbeat()
            except Exception as e:
                log.error(f"Heartbeat error: {e}")
            
            time.sleep(self._heartbeat_interval)
    
    def _emit_heartbeat(self):
        """Emit heartbeat with system stats."""
        with self._lock:
            active_sessions = sum(1 for s in self.sessions.values() if s.state == "processing")
            waiting_sessions = sum(1 for s in self.sessions.values() if s.state == "waiting")
            total_queue = sum(s.queue_depth for s in self.sessions.values())
            
            # Check for stuck sessions (processing for > 2 minutes)
            now = time.time()
            for session in self.sessions.values():
                if session.state == "processing":
                    age = now - session.last_activity
                    if age > 120:
                        log.warning(
                            f"Stuck session detected: session_id={session.session_id} "
                            f"age={age:.0f}s state={session.state}"
                        )
        
        # Only log heartbeat if there's activity
        if self.stats["requests_received"] > 0 or active_sessions > 0:
            log.debug(
                f"Heartbeat: requests={self.stats['requests_received']}/"
                f"{self.stats['requests_processed']}/{self.stats['requests_errors']} "
                f"active={active_sessions} waiting={waiting_sessions} queued={total_queue}"
            )
    
    # Stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current diagnostic stats."""
        with self._lock:
            return {
                "sessions": {
                    "total": len(self.sessions),
                    "active": sum(1 for s in self.sessions.values() if s.state == "processing"),
                    "waiting": sum(1 for s in self.sessions.values() if s.state == "waiting"),
                    "idle": sum(1 for s in self.sessions.values() if s.state == "idle"),
                },
                "requests": {
                    "received": self.stats["requests_received"],
                    "processed": self.stats["requests_processed"],
                    "errors": self.stats["requests_errors"],
                },
                "last_activity": self.stats["last_activity"],
            }
    
    def reset(self):
        """Reset all tracking (for testing)."""
        with self._lock:
            self.sessions.clear()
            self.stats = {
                "requests_received": 0,
                "requests_processed": 0,
                "requests_errors": 0,
                "last_activity": 0,
            }


# Singleton instance
_tracker = DiagnosticTracker()


# Public API
def get_tracker() -> DiagnosticTracker:
    """Get the diagnostic tracker instance."""
    return _tracker


def log_session_start(session_id: str):
    _tracker.log_session_start(session_id)


def log_session_end(session_id: str, outcome: str = "completed"):
    _tracker.log_session_end(session_id, outcome)


def log_request_received(session_id: str, request_type: str, metadata: Optional[Dict[str, Any]] = None):
    _tracker.log_request_received(session_id, request_type, metadata)


def log_request_processed(
    session_id: str,
    request_type: str,
    duration_ms: float,
    outcome: str = "success",
    error: Optional[str] = None
):
    _tracker.log_request_processed(session_id, request_type, duration_ms, outcome, error)


def log_tool_execution(
    session_id: str,
    tool_name: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None
):
    _tracker.log_tool_execution(session_id, tool_name, duration_ms, success, error)


def start_heartbeat(interval: int = 30):
    _tracker.start_heartbeat(interval)


def stop_heartbeat():
    _tracker.stop_heartbeat()


def get_diagnostic_stats() -> Dict[str, Any]:
    return _tracker.get_stats()
