"""
Tests for Agent Trace System

Tests:
- Session creation and lifecycle
- Turn tracing
- LLM request/response tracing
- Tool call tracing
- Thinking capture
- JSONL output format
"""
import os
import json
import tempfile
import shutil
import unittest
from pathlib import Path


class TestAgentTrace(unittest.TestCase):
    """Tests for the agent trace module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        from backend.core.agent_trace import configure_tracer
        configure_tracer(
            enabled=True,
            trace_dir=self.temp_dir,
            sample_rate=1.0,
            include_messages=True,
            include_thinking=True
        )
    
    def tearDown(self):
        """Clean up temp files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_session(self):
        """Test session creation."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="test-session-1")
        
        self.assertEqual(session.session_id, "test-session-1")
        
        # Session directory should be created
        session_dir = Path(self.temp_dir) / "session-test-session-1"
        self.assertTrue(session_dir.exists())
        
        # Metadata file should exist
        metadata_file = session_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
    
    def test_session_lifecycle(self):
        """Test session start/end."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="lifecycle-test")
        session.start_session(metadata={"persona": "test"})
        session.end_session(outcome="completed")
        
        # Read events file
        events_file = Path(self.temp_dir) / "session-lifecycle-test" / "events.jsonl"
        self.assertTrue(events_file.exists())
        
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "session.start")
        self.assertEqual(events[1]["event_type"], "session.end")
        self.assertEqual(events[1]["data"]["outcome"], "completed")
    
    def test_turn_tracing(self):
        """Test turn start/end."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="turn-test")
        session.start_session()
        
        run_id = session.start_turn("Hello, agent!")
        self.assertIsNotNone(run_id)
        self.assertTrue(run_id.startswith("run-"))
        
        session.end_turn("Hello! How can I help?")
        session.end_session()
        
        # Read events
        events_file = Path(self.temp_dir) / "session-turn-test" / "events.jsonl"
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        turn_events = [e for e in events if e["event_type"].startswith("turn.")]
        self.assertEqual(len(turn_events), 2)
        self.assertEqual(turn_events[0]["data"]["user_input"], "Hello, agent!")
        self.assertEqual(turn_events[1]["data"]["output"], "Hello! How can I help?")
    
    def test_llm_tracing(self):
        """Test LLM request/response tracing."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="llm-test")
        session.start_session()
        session.start_turn("Test input")
        
        # Log LLM request
        session.log_llm_request(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            tools=["web_search"]
        )
        
        # Log LLM response
        session.log_llm_response(
            model="gpt-4",
            content="Test response",
            tokens={"prompt": 100, "completion": 50},
            duration_ms=1500.0,
            thinking="I should search the web first..."
        )
        
        session.end_turn("Test response")
        session.end_session()
        
        # Read events
        events_file = Path(self.temp_dir) / "session-llm-test" / "events.jsonl"
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        llm_events = [e for e in events if e["event_type"].startswith("llm.")]
        self.assertEqual(len(llm_events), 2)
        
        # Check request
        self.assertEqual(llm_events[0]["event_type"], "llm.request")
        self.assertEqual(llm_events[0]["data"]["model"], "gpt-4")
        self.assertEqual(llm_events[0]["data"]["tools"], ["web_search"])
        
        # Check response
        self.assertEqual(llm_events[1]["event_type"], "llm.response")
        self.assertEqual(llm_events[1]["data"]["tokens"]["prompt"], 100)
        self.assertIn("thinking", llm_events[1]["data"])
    
    def test_tool_tracing(self):
        """Test tool call/result tracing."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="tool-test")
        session.start_session()
        session.start_turn("Search for Python docs")
        
        # Log tool call
        session.log_tool_call(
            tool_name="web_search",
            args={"query": "Python documentation"}
        )
        
        # Log tool result
        session.log_tool_result(
            tool_name="web_search",
            success=True,
            result="Found 10 results...",
            duration_ms=500.0
        )
        
        session.end_turn("Here are the results")
        session.end_session()
        
        # Read events
        events_file = Path(self.temp_dir) / "session-tool-test" / "events.jsonl"
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        tool_events = [e for e in events if e["event_type"].startswith("tool.")]
        self.assertEqual(len(tool_events), 2)
        
        self.assertEqual(tool_events[0]["event_type"], "tool.call")
        self.assertEqual(tool_events[0]["data"]["tool_name"], "web_search")
        
        self.assertEqual(tool_events[1]["event_type"], "tool.result")
        self.assertTrue(tool_events[1]["data"]["success"])
    
    def test_thinking_capture(self):
        """Test thinking/reasoning capture."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="thinking-test")
        session.start_session()
        session.start_turn("Complex reasoning task")
        
        session.log_thinking(
            thinking="Let me break this problem down step by step...",
            stage="planning"
        )
        
        session.end_turn("Here's my analysis")
        session.end_session()
        
        # Read events
        events_file = Path(self.temp_dir) / "session-thinking-test" / "events.jsonl"
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        thinking_events = [e for e in events if e["event_type"] == "thinking"]
        self.assertEqual(len(thinking_events), 1)
        self.assertEqual(thinking_events[0]["data"]["stage"], "planning")
        self.assertIn("token_estimate", thinking_events[0]["data"])
    
    def test_context_manager(self):
        """Test context manager usage."""
        from backend.core.agent_trace import trace_session, trace_turn
        
        with trace_session(session_id="context-test") as session:
            with trace_turn(session, "Hello!"):
                session.log_llm_response(
                    model="gpt-4",
                    content="Hi there!",
                    duration_ms=100.0
                )
        
        # Events should be logged
        events_file = Path(self.temp_dir) / "session-context-test" / "events.jsonl"
        self.assertTrue(events_file.exists())
        
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        # Should have: session.start, turn.start, llm.response, session.end
        self.assertGreaterEqual(len(events), 3)
    
    def test_content_truncation(self):
        """Test that long content is truncated."""
        from backend.core.agent_trace import create_session, configure_tracer
        
        configure_tracer(max_content_length=100)
        
        session = create_session(session_id="truncate-test")
        session.start_session()
        
        long_input = "x" * 500
        session.start_turn(long_input)
        session.end_turn("response")
        session.end_session()
        
        # Read events
        events_file = Path(self.temp_dir) / "session-truncate-test" / "events.jsonl"
        with open(events_file) as f:
            events = [json.loads(line) for line in f]
        
        turn_start = [e for e in events if e["event_type"] == "turn.start"][0]
        self.assertIn("truncated", turn_start["data"]["user_input"])
        self.assertLess(len(turn_start["data"]["user_input"]), 500)
    
    def test_jsonl_format(self):
        """Test that output is valid JSONL."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="jsonl-test")
        session.start_session()
        session.start_turn("test")
        session.end_turn("test")
        session.end_session()
        
        events_file = Path(self.temp_dir) / "session-jsonl-test" / "events.jsonl"
        
        # Each line should be valid JSON
        with open(events_file) as f:
            for line in f:
                data = json.loads(line)
                self.assertIn("timestamp", data)
                self.assertIn("event_type", data)
                self.assertIn("session_id", data)


class TestTraceAnalysis(unittest.TestCase):
    """Tests for trace analysis utilities."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        from backend.core.agent_trace import configure_tracer
        configure_tracer(enabled=True, trace_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_grep_friendly_format(self):
        """Test that traces can be grepped for analysis."""
        from backend.core.agent_trace import create_session
        
        session = create_session(session_id="grep-test")
        session.start_session()
        run_id = session.start_turn("Search query")
        session.log_tool_call("web_search", {"query": "test"})
        session.log_tool_result("web_search", success=True)
        session.end_turn("Results")
        session.end_session()
        
        # Read file as text for grep simulation
        events_file = Path(self.temp_dir) / "session-grep-test" / "events.jsonl"
        with open(events_file) as f:
            content = f.read()
        
        # Grep for run_id should find multiple lines
        lines_with_run_id = [line for line in content.split("\n") if run_id in line]
        self.assertGreaterEqual(len(lines_with_run_id), 3)


if __name__ == "__main__":
    unittest.main()
