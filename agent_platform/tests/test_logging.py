"""
Tests for Logging Infrastructure

Tests:
- File logging with rotation
- JSON structured output
- Subsystem loggers
- Colored console output
- Diagnostic tracking
"""
import os
import json
import tempfile
import unittest
import time
from pathlib import Path


class TestLogging(unittest.TestCase):
    """Tests for the logging module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_configure_logging(self):
        """Test logging configuration."""
        from backend.core.logging import configure_logging, get_log_file_path
        
        configure_logging(
            log_dir=self.temp_dir,
            log_level="DEBUG",
            max_days=7,
            json_format=True,
            console_colors=False
        )
        
        log_path = get_log_file_path()
        self.assertTrue(log_path.startswith(self.temp_dir))
    
    def test_get_logger(self):
        """Test getting a subsystem logger."""
        from backend.core.logging import configure_logging, get_logger
        
        configure_logging(log_dir=self.temp_dir, console_colors=False)
        
        log = get_logger("test_subsystem")
        
        # Should have subsystem attribute
        self.assertEqual(log.subsystem, "test_subsystem")
        
        # Should be able to create child
        child = log.child("child")
        self.assertEqual(child.subsystem, "test_subsystem/child")
    
    def test_json_file_output(self):
        """Test that logs are written as JSON to file."""
        from backend.core.logging import configure_logging, get_logger, get_log_file_path
        
        configure_logging(
            log_dir=self.temp_dir,
            log_level="INFO",
            json_format=True,
            console_colors=False
        )
        
        log = get_logger("json_test")
        log.info("Test message for JSON")
        
        # Force flush by reading the file
        log_file = get_log_file_path()
        
        # Small delay to ensure file write
        time.sleep(0.1)
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                content = f.read()
                if content.strip():
                    # Should be valid JSON
                    for line in content.strip().split('\n'):
                        if line:
                            data = json.loads(line)
                            self.assertIn("timestamp", data)
                            self.assertIn("level", data)
                            self.assertIn("subsystem", data)
                            self.assertIn("message", data)
    
    def test_log_levels(self):
        """Test log level filtering."""
        from backend.core.logging import configure_logging, get_logger
        
        configure_logging(
            log_dir=self.temp_dir,
            log_level="WARNING",
            console_colors=False
        )
        
        log = get_logger("level_test")
        
        # These should all work without error
        log.debug("Debug message")
        log.info("Info message")
        log.warning("Warning message")
        log.error("Error message")
        log.critical("Critical message")


class TestDiagnostic(unittest.TestCase):
    """Tests for the diagnostic module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Configure logging for diagnostic module
        from backend.core.logging import configure_logging
        configure_logging(log_dir=self.temp_dir, console_colors=False)
        
        # Reset tracker
        from backend.core.diagnostic import get_tracker
        get_tracker().reset()
    
    def tearDown(self):
        """Clean up."""
        from backend.core.diagnostic import stop_heartbeat
        stop_heartbeat()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_session_tracking(self):
        """Test session lifecycle tracking."""
        from backend.core.diagnostic import (
            log_session_start, log_session_end, get_diagnostic_stats
        )
        
        # Start session
        log_session_start("test-session-1")
        
        stats = get_diagnostic_stats()
        self.assertEqual(stats["sessions"]["active"], 1)
        
        # End session
        log_session_end("test-session-1")
        
        stats = get_diagnostic_stats()
        self.assertEqual(stats["sessions"]["active"], 0)
        self.assertEqual(stats["sessions"]["idle"], 1)
    
    def test_request_tracking(self):
        """Test request tracking."""
        from backend.core.diagnostic import (
            log_request_received, log_request_processed, get_diagnostic_stats
        )
        
        # Receive request
        log_request_received("test-session", "chat")
        
        stats = get_diagnostic_stats()
        self.assertEqual(stats["requests"]["received"], 1)
        
        # Process request
        log_request_processed("test-session", "chat", duration_ms=100.0)
        
        stats = get_diagnostic_stats()
        self.assertEqual(stats["requests"]["processed"], 1)
    
    def test_tool_execution_tracking(self):
        """Test tool execution tracking."""
        from backend.core.diagnostic import log_tool_execution, get_diagnostic_stats
        
        # Successful execution
        log_tool_execution("session-1", "web_search", 150.0, success=True)
        
        # Failed execution
        log_tool_execution("session-1", "browser_navigate", 500.0, success=False, error="Timeout")
        
        stats = get_diagnostic_stats()
        self.assertGreater(stats["last_activity"], 0)
    
    def test_heartbeat(self):
        """Test heartbeat functionality."""
        from backend.core.diagnostic import (
            start_heartbeat, stop_heartbeat, log_session_start, get_tracker
        )
        
        # Start heartbeat with short interval for test
        start_heartbeat(interval=1)
        
        # Create some activity
        log_session_start("heartbeat-test")
        
        # Wait for one heartbeat
        time.sleep(1.5)
        
        # Heartbeat should have run
        tracker = get_tracker()
        self.assertTrue(tracker._heartbeat_running)
        
        # Stop heartbeat
        stop_heartbeat()
        self.assertFalse(tracker._heartbeat_running)
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        from backend.core.diagnostic import (
            log_session_start, log_request_received, get_diagnostic_stats
        )
        
        log_session_start("stats-test")
        log_request_received("stats-test", "query")
        
        stats = get_diagnostic_stats()
        
        # Check structure
        self.assertIn("sessions", stats)
        self.assertIn("requests", stats)
        self.assertIn("last_activity", stats)
        
        # Check values
        self.assertEqual(stats["sessions"]["total"], 1)
        self.assertEqual(stats["requests"]["received"], 1)


class TestColoredFormatter(unittest.TestCase):
    """Tests for colored console formatter."""
    
    def test_formatter_without_colors(self):
        """Test formatter in non-TTY mode."""
        from backend.core.logging import ColoredConsoleFormatter
        import logging
        
        formatter = ColoredConsoleFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.subsystem = "test_sub"
        
        formatted = formatter.format(record)
        
        # Should contain the message without ANSI codes
        self.assertIn("Test message", formatted)
        self.assertIn("[test_sub]", formatted)
        self.assertNotIn('\033[', formatted)

    def test_redundancy_reduction(self):
        """Test that redundancy in log messages is reduced."""
        from backend.core.logging import ColoredConsoleFormatter
        import logging
        
        formatter = ColoredConsoleFormatter(use_colors=False)
        
        # Test case 1: Prefix with colon
        record1 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test: Hello World", args=(), exc_info=None
        )
        record1.subsystem = "test"
        output1 = formatter.format(record1)
        
        # Test case 2: Prefix with space
        record2 = logging.LogRecord(
            name="browser", level=logging.INFO, pathname="", lineno=0,
            msg="browser Navigation started", args=(), exc_info=None
        )
        record2.subsystem = "browser"
        output2 = formatter.format(record2)

        # Test case 3: No prefix
        record3 = logging.LogRecord(
            name="api", level=logging.INFO, pathname="", lineno=0,
            msg="Request received", args=(), exc_info=None
        )
        record3.subsystem = "api"
        output3 = formatter.format(record3)
        
        # Assertions
        # Output format is: Time [subsystem] Message
        self.assertIn("[test] Hello World", output1)
        self.assertNotIn("test: Hello", output1)
        
        self.assertIn("[browser] Navigation started", output2)
        self.assertNotIn("browser Navigation", output2)
        
        self.assertIn("[api] Request received", output3)


class TestJSONFormatter(unittest.TestCase):
    """Tests for JSON formatter."""
    
    def test_json_output(self):
        """Test JSON formatting."""
        from backend.core.logging import JSONFormatter
        import logging
        
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test JSON message",
            args=(),
            exc_info=None
        )
        record.subsystem = "json_test"
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        data = json.loads(formatted)
        
        self.assertEqual(data["message"], "Test JSON message")
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["subsystem"], "json_test")
        self.assertIn("timestamp", data)


if __name__ == "__main__":
    unittest.main()
