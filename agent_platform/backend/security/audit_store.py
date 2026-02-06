"""
Audit Store
JSON Lines based persistence for audit logs.
"""
import json
import os
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Iterator
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: float
    event_type: str
    severity: str  # "info", "warning", "critical"
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AuditStore:
    """
    JSON Lines based audit log storage.
    
    Stores logs in daily files: audit/YYYY-MM-DD.jsonl
    """
    
    def __init__(self, store_path: str = "./data/audit"):
        self.store_path = Path(store_path)
    
    def _ensure_dir(self) -> None:
        """Ensure store directory exists."""
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def _get_log_file(self, log_date: Optional[date] = None) -> Path:
        """Get the log file path for a date."""
        if log_date is None:
            log_date = date.today()
        return self.store_path / f"{log_date.isoformat()}.jsonl"
    
    def append(self, entry: AuditEntry) -> None:
        """Append an entry to the current day's log."""
        self._ensure_dir()
        
        log_file = self._get_log_file()
        
        try:
            with open(log_file, 'a') as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def read_entries(
        self,
        log_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[AuditEntry]:
        """Read entries from a log file."""
        log_file = self._get_log_file(log_date)
        
        if not log_file.exists():
            return []
        
        entries = []
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entries.append(AuditEntry.from_dict(data))
                        if limit and len(entries) >= limit:
                            break
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
        
        return entries
    
    def read_recent(self, count: int = 100) -> List[AuditEntry]:
        """Read the most recent entries across all log files."""
        entries = []
        
        # Get all log files sorted by date descending
        log_files = sorted(
            self.store_path.glob("*.jsonl"),
            key=lambda p: p.stem,
            reverse=True
        )
        
        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entries.append(AuditEntry.from_dict(data))
                        if len(entries) >= count:
                            return entries
            except Exception as e:
                logger.error(f"Failed to read {log_file}: {e}")
        
        return entries
    
    def search(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        session_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Search audit logs with filters."""
        entries = []
        
        # Determine date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date
        
        # Get log files in range
        current = end_date
        while current >= start_date:
            log_file = self._get_log_file(current)
            
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            
                            data = json.loads(line)
                            
                            # Apply filters
                            if event_type and data.get("event_type") != event_type:
                                continue
                            if severity and data.get("severity") != severity:
                                continue
                            if session_id and data.get("session_id") != session_id:
                                continue
                            
                            entries.append(AuditEntry.from_dict(data))
                            
                            if len(entries) >= limit:
                                return entries
                                
                except Exception as e:
                    logger.error(f"Failed to search {log_file}: {e}")
            
            # Move to previous day
            from datetime import timedelta
            current = current - timedelta(days=1)
        
        return entries
    
    def cleanup_old_logs(self, keep_days: int = 30) -> int:
        """Delete log files older than keep_days."""
        from datetime import timedelta
        
        cutoff = date.today() - timedelta(days=keep_days)
        deleted = 0
        
        for log_file in self.store_path.glob("*.jsonl"):
            try:
                file_date = date.fromisoformat(log_file.stem)
                if file_date < cutoff:
                    log_file.unlink()
                    deleted += 1
            except ValueError:
                continue
        
        if deleted:
            logger.info(f"Cleaned up {deleted} old audit log files")
        
        return deleted
