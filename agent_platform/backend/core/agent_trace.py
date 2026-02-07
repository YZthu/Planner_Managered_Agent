"""
Agent Trace System

A dedicated JSONL-based tracing system for multi-turn LLM agent behavior.
Designed for debugging and analysis, with clear upgrade path to LangFuse/OpenTelemetry.

Trace Events:
- session.start / session.end
- turn.start / turn.end  
- llm.request / llm.response
- tool.call / tool.result
- thinking (for reasoning models)

Directory Structure:
    traces/
    └── session-{session_id}/
        ├── metadata.json      # Session metadata
        └── events.jsonl       # All events for this session
"""
import os
import json
import time
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from contextlib import contextmanager

# Default configuration
DEFAULT_TRACE_DIR = "./traces"
DEFAULT_ENABLED = True
DEFAULT_SAMPLE_RATE = 1.0  # 100% sampling by default


@dataclass
class TraceConfig:
    """Configuration for the trace system."""
    enabled: bool = DEFAULT_ENABLED
    trace_dir: str = DEFAULT_TRACE_DIR
    sample_rate: float = DEFAULT_SAMPLE_RATE
    include_messages: bool = True
    include_thinking: bool = True
    max_content_length: int = 10000  # Truncate long content


@dataclass
class TraceEvent:
    """A single trace event."""
    timestamp: str
    event_type: str
    session_id: str
    run_id: Optional[str] = None
    turn: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class SessionTrace:
    """Manages tracing for a single agent session."""
    
    def __init__(
        self,
        session_id: str,
        trace_dir: str,
        config: TraceConfig,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.session_id = session_id
        self.trace_dir = trace_dir
        self.config = config
        self.session_dir = Path(trace_dir) / f"session-{session_id}"
        self.events_file = self.session_dir / "events.jsonl"
        self.metadata_file = self.session_dir / "metadata.json"
        
        self._turn = 0
        self._run_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()
        
        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Write metadata
        session_metadata = {
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            **(metadata or {})
        }
        with open(self.metadata_file, "w") as f:
            json.dump(session_metadata, f, indent=2)
    
    def _write_event(self, event: TraceEvent):
        """Write event to JSONL file."""
        if not self.config.enabled:
            return
        
        with self._lock:
            with open(self.events_file, "a") as f:
                f.write(json.dumps(asdict(event), default=str) + "\n")
    
    def _now(self) -> str:
        """Get current ISO timestamp."""
        return datetime.utcnow().isoformat() + "Z"
    
    def _truncate(self, content: Any) -> Any:
        """Truncate content if too long."""
        if isinstance(content, str) and len(content) > self.config.max_content_length:
            return content[:self.config.max_content_length] + f"... [truncated {len(content) - self.config.max_content_length} chars]"
        return content
    
    # Session lifecycle
    
    def start_session(self, metadata: Optional[Dict[str, Any]] = None):
        """Log session start."""
        self._start_time = time.time()
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="session.start",
            session_id=self.session_id,
            data=metadata or {}
        ))
    
    def end_session(self, outcome: str = "completed", metadata: Optional[Dict[str, Any]] = None):
        """Log session end."""
        duration_ms = (time.time() - self._start_time) * 1000 if self._start_time else None
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="session.end",
            session_id=self.session_id,
            duration_ms=duration_ms,
            data={"outcome": outcome, "total_turns": self._turn, **(metadata or {})}
        ))
    
    # Turn lifecycle
    
    def start_turn(self, user_input: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new conversation turn. Returns run_id."""
        self._turn += 1
        self._run_id = f"run-{uuid.uuid4().hex[:12]}"
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="turn.start",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            data={
                "user_input": self._truncate(user_input) if self.config.include_messages else "[redacted]",
                **(metadata or {})
            }
        ))
        return self._run_id
    
    def end_turn(self, output: str, metadata: Optional[Dict[str, Any]] = None):
        """End the current turn."""
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="turn.end",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            data={
                "output": self._truncate(output) if self.config.include_messages else "[redacted]",
                **(metadata or {})
            }
        ))
    
    # LLM tracing
    
    def log_llm_request(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log LLM request."""
        data = {
            "model": model,
            "message_count": len(messages),
        }
        if self.config.include_messages:
            data["messages"] = [self._truncate(m) for m in messages]
        if tools:
            data["tools"] = tools
        if metadata:
            data.update(metadata)
        
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="llm.request",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            data=data
        ))
    
    def log_llm_response(
        self,
        model: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tokens: Optional[Dict[str, int]] = None,
        duration_ms: Optional[float] = None,
        thinking: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log LLM response."""
        data = {
            "model": model,
        }
        if self.config.include_messages:
            data["content"] = self._truncate(content)
        if tool_calls:
            data["tool_calls"] = [{"name": tc.get("name", "unknown")} for tc in tool_calls]
        if tokens:
            data["tokens"] = tokens
        if thinking and self.config.include_thinking:
            data["thinking"] = self._truncate(thinking)
            data["thinking_tokens"] = len(thinking.split()) if thinking else 0
        if metadata:
            data.update(metadata)
        
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="llm.response",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            duration_ms=duration_ms,
            error=error,
            data=data
        ))
    
    # Tool tracing
    
    def log_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log tool invocation."""
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="tool.call",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            data={
                "tool_name": tool_name,
                "args": {k: self._truncate(v) for k, v in args.items()},
                **(metadata or {})
            }
        ))
    
    def log_tool_result(
        self,
        tool_name: str,
        success: bool,
        result: Any = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log tool result."""
        data = {
            "tool_name": tool_name,
            "success": success,
        }
        if result is not None and self.config.include_messages:
            data["result"] = self._truncate(str(result))
        if metadata:
            data.update(metadata)
        
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="tool.result",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            duration_ms=duration_ms,
            error=error,
            data=data
        ))
    
    # Thinking/Reasoning
    
    def log_thinking(
        self,
        thinking: str,
        stage: str = "reasoning",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log thinking/reasoning process (for o1/Claude extended thinking)."""
        if not self.config.include_thinking:
            return
        
        self._write_event(TraceEvent(
            timestamp=self._now(),
            event_type="thinking",
            session_id=self.session_id,
            run_id=self._run_id,
            turn=self._turn,
            data={
                "stage": stage,
                "content": self._truncate(thinking),
                "token_estimate": len(thinking.split()),
                **(metadata or {})
            }
        ))


class AgentTracer:
    """Global agent tracing manager."""
    
    _instance: Optional["AgentTracer"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = TraceConfig()
        self.sessions: Dict[str, SessionTrace] = {}
        self._lock = threading.Lock()
        self._initialized = True
    
    def configure(
        self,
        enabled: Optional[bool] = None,
        trace_dir: Optional[str] = None,
        sample_rate: Optional[float] = None,
        include_messages: Optional[bool] = None,
        include_thinking: Optional[bool] = None,
        max_content_length: Optional[int] = None
    ):
        """Configure the tracer."""
        if enabled is not None:
            self.config.enabled = enabled
        if trace_dir is not None:
            self.config.trace_dir = trace_dir
        if sample_rate is not None:
            self.config.sample_rate = sample_rate
        if include_messages is not None:
            self.config.include_messages = include_messages
        if include_thinking is not None:
            self.config.include_thinking = include_thinking
        if max_content_length is not None:
            self.config.max_content_length = max_content_length
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionTrace:
        """Create a new session trace."""
        if session_id is None:
            session_id = uuid.uuid4().hex[:16]
        
        # Apply sampling
        import random
        if random.random() > self.config.sample_rate:
            # Return a no-op session
            self.config.enabled = False
        
        session = SessionTrace(
            session_id=session_id,
            trace_dir=self.config.trace_dir,
            config=self.config,
            metadata=metadata
        )
        
        with self._lock:
            self.sessions[session_id] = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionTrace]:
        """Get an existing session trace."""
        return self.sessions.get(session_id)
    
    @contextmanager
    def trace_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager for session tracing."""
        session = self.create_session(session_id, metadata)
        session.start_session(metadata)
        try:
            yield session
        except Exception as e:
            session.end_session(outcome="error", metadata={"error": str(e)})
            raise
        else:
            session.end_session(outcome="completed")
    
    @contextmanager
    def trace_turn(
        self,
        session: SessionTrace,
        user_input: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Context manager for turn tracing."""
        run_id = session.start_turn(user_input, metadata)
        try:
            yield run_id
        except Exception as e:
            session.end_turn(output="", metadata={"error": str(e)})
            raise


# Singleton instance
_tracer = AgentTracer()


# Public API
def configure_tracer(**kwargs):
    """Configure the agent tracer."""
    _tracer.configure(**kwargs)


def create_session(
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> SessionTrace:
    """Create a new session trace."""
    return _tracer.create_session(session_id, metadata)


def get_session(session_id: str) -> Optional[SessionTrace]:
    """Get an existing session trace."""
    return _tracer.get_session(session_id)


def trace_session(
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Context manager for session tracing."""
    return _tracer.trace_session(session_id, metadata)


def trace_turn(
    session: SessionTrace,
    user_input: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Context manager for turn tracing."""
    return _tracer.trace_turn(session, user_input, metadata)
