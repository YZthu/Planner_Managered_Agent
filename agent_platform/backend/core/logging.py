"""
Logging Infrastructure Module

Provides:
- File logging with daily rotation
- JSON structured output
- Subsystem loggers with colored prefixes
- Configurable log levels
"""
import os
import sys
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from typing import Optional, Dict, Any
from functools import lru_cache
from zoneinfo import ZoneInfo

# Default configuration
DEFAULT_LOG_DIR = "./logs"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_DAYS = 15
DEFAULT_JSON_FORMAT = True
DEFAULT_TIMEZONE = "UTC"


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""
    
    def __init__(self, tz: Optional[ZoneInfo] = None):
        super().__init__()
        self.tz = tz

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(self.tz).isoformat(),
            "level": record.levelname,
            "subsystem": getattr(record, 'subsystem', record.name),
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, 'extra') and record.extra:
            log_record.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console output with subsystem prefixes."""
    
    COLORS = {
        'DEBUG': '\033[90m',     # Gray
        'INFO': '\033[36m',      # Cyan
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    # Subsystem colors (hash-based)
    SUBSYSTEM_COLORS = ['\033[36m', '\033[32m', '\033[33m', '\033[34m', '\033[35m', '\033[31m']
    
    def __init__(self, use_colors: bool = True, tz: Optional[ZoneInfo] = None):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
        self.tz = tz
    
    def _subsystem_color(self, subsystem: str) -> str:
        """Pick color based on subsystem name hash."""
        hash_val = sum(ord(c) for c in subsystem)
        return self.SUBSYSTEM_COLORS[hash_val % len(self.SUBSYSTEM_COLORS)]
    
    def format(self, record: logging.LogRecord) -> str:
        subsystem = getattr(record, 'subsystem', record.name)
        # Shorten module path for display
        if subsystem.startswith('backend.'):
            subsystem = subsystem.replace('backend.', '')
        
        timestamp = datetime.now(self.tz).strftime('%H:%M:%S')
        level = record.levelname
        message = record.getMessage()

        # Redundancy reduction: remove subsystem prefix if it matches
        # E.g. "browser: Navigation started" -> "Navigation started"
        prefix = f"{subsystem}: "
        if message.lower().startswith(prefix.lower()):
            message = message[len(prefix):]
        # Also handle space separator if colon is missing but word matches exactly
        elif message.lower().startswith(f"{subsystem} ".lower()):
             message = message[len(subsystem)+1:]
        
        if self.use_colors:
            level_color = self.COLORS.get(level, '')
            sub_color = self._subsystem_color(subsystem)
            return f"\033[90m{timestamp}\033[0m {sub_color}[{subsystem}]\033[0m {level_color}{message}\033[0m"
        else:
            return f"{timestamp} [{subsystem}] {message}"


class SubsystemLogger(logging.LoggerAdapter):
    """Logger adapter that adds subsystem context."""
    
    def __init__(self, logger: logging.Logger, subsystem: str):
        super().__init__(logger, {'subsystem': subsystem})
        self.subsystem = subsystem
    
    def process(self, msg, kwargs):
        # Add subsystem to extra
        kwargs.setdefault('extra', {})
        kwargs['extra']['subsystem'] = self.subsystem
        return msg, kwargs
    
    def child(self, name: str) -> "SubsystemLogger":
        """Create a child logger with extended subsystem path."""
        child_subsystem = f"{self.subsystem}/{name}"
        return SubsystemLogger(self.logger, child_subsystem)


class LoggingManager:
    """Centralized logging configuration manager."""
    
    _instance: Optional["LoggingManager"] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LoggingManager._initialized:
            return
        
        self.log_dir = DEFAULT_LOG_DIR
        self.log_level = DEFAULT_LOG_LEVEL
        self.max_days = DEFAULT_MAX_DAYS
        self.json_format = DEFAULT_JSON_FORMAT
        self.timezone = DEFAULT_TIMEZONE
        self.tz_info: Optional[ZoneInfo] = None
        self.root_logger: Optional[logging.Logger] = None
        self._file_handler: Optional[TimedRotatingFileHandler] = None
        self._console_handler: Optional[logging.StreamHandler] = None
    
    def configure(
        self,
        log_dir: Optional[str] = None,
        log_level: Optional[str] = None,
        max_days: Optional[int] = None,
        json_format: Optional[bool] = None,
        console_colors: bool = True,
        timezone: str = "UTC"
    ):
        """Configure the logging system."""
        if log_dir:
            self.log_dir = log_dir
        if log_level:
            self.log_level = log_level.upper()
        if max_days is not None:
            self.max_days = max_days
        if json_format is not None:
            self.json_format = json_format
        
        if timezone:
            self.timezone = timezone
            try:
                self.tz_info = ZoneInfo(timezone)
            except Exception:
                self.tz_info = None

        self._setup_logging(console_colors)
        LoggingManager._initialized = True
    
    def _setup_logging(self, console_colors: bool = True):
        """Set up logging handlers."""
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Get root logger for agent_platform
        self.root_logger = logging.getLogger("agent_platform")
        self.root_logger.setLevel(getattr(logging, self.log_level))
        
        # Clear existing handlers
        self.root_logger.handlers.clear()
        
        # File handler with daily rotation
        log_file = os.path.join(self.log_dir, "agent.log")
        self._file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=self.max_days,
            encoding="utf-8"
        )
        self._file_handler.suffix = "%Y-%m-%d"
        
        # Use JSON formatter for file
        if self.json_format:
            self._file_handler.setFormatter(JSONFormatter(tz=self.tz_info))
        else:
            # Fallback to simple formatter, injecting local time which usually follows system
            # But strictly we should use formatter with tz.
            # Simplified for non-json
            self._file_handler.setFormatter(
                logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
            )
        
        self.root_logger.addHandler(self._file_handler)
        
        # Console handler with colors
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setFormatter(ColoredConsoleFormatter(use_colors=console_colors, tz=self.tz_info))
        self.root_logger.addHandler(self._console_handler)
        
        # Prevent propagation to root logger
        self.root_logger.propagate = False
    
    def get_log_file_path(self) -> str:
        """Get the current log file path."""
        return os.path.join(self.log_dir, "agent.log")
    
    def get_subsystem_logger(self, subsystem: str) -> SubsystemLogger:
        """Get a logger for a specific subsystem."""
        if not self.root_logger:
            self.configure()
        return SubsystemLogger(self.root_logger, subsystem)


# Singleton instance
_manager = LoggingManager()


def configure_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    max_days: Optional[int] = None,
    json_format: Optional[bool] = None,
    console_colors: bool = True,
    timezone: str = "UTC"
):
    """Configure the logging system. Call once at startup."""
    _manager.configure(
        log_dir=log_dir,
        log_level=log_level,
        max_days=max_days,
        json_format=json_format,
        console_colors=console_colors,
        timezone=timezone
    )


def get_logger(subsystem: str) -> SubsystemLogger:
    """
    Get a subsystem logger.
    
    Usage:
        log = get_logger("browser")
        log.info("Browser initialized")
        
        child = log.child("navigate")
        child.debug("Navigating to URL")
    """
    return _manager.get_subsystem_logger(subsystem)


def get_log_file_path() -> str:
    """Get the current log file path."""
    return _manager.get_log_file_path()


# Convenience aliases for common subsystems
@lru_cache(maxsize=32)
def _cached_logger(subsystem: str) -> SubsystemLogger:
    return get_logger(subsystem)


def agent_logger() -> SubsystemLogger:
    return _cached_logger("agent")


def browser_logger() -> SubsystemLogger:
    return _cached_logger("browser")


def api_logger() -> SubsystemLogger:
    return _cached_logger("api")


def plugin_logger() -> SubsystemLogger:
    return _cached_logger("plugins")
