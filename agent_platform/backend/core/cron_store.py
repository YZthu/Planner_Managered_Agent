"""
Cron Store
JSON-based persistence for scheduled cron jobs.
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
class CronJob:
    """Represents a scheduled cron job."""
    id: str
    expression: str  # Cron expression (e.g. "0 9 * * *")
    task: str  # Task description/prompt to execute
    enabled: bool = True
    next_run: Optional[float] = None  # Unix timestamp
    last_run: Optional[float] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    run_count: int = 0
    session_id: Optional[str] = None  # Session to run in
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CronJob":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CronStoreFile:
    """Cron store file structure."""
    version: int = 1
    jobs: List[CronJob] = field(default_factory=list)


class CronStore:
    """JSON-based cron job persistence."""
    
    def __init__(self, store_path: str = "./data/cron/jobs.json"):
        self.store_path = Path(store_path)
        self._jobs: Dict[str, CronJob] = {}
        self._loaded = False
    
    def _ensure_dir(self) -> None:
        """Ensure store directory exists."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> None:
        """Load jobs from disk."""
        if not self.store_path.exists():
            self._jobs = {}
            self._loaded = True
            return
        
        try:
            with open(self.store_path, 'r') as f:
                data = json.load(f)
            
            jobs_data = data.get("jobs", [])
            self._jobs = {}
            for job_data in jobs_data:
                if job_data:
                    job = CronJob.from_dict(job_data)
                    self._jobs[job.id] = job
            
            self._loaded = True
            logger.debug(f"Loaded {len(self._jobs)} cron jobs from {self.store_path}")
            
        except Exception as e:
            logger.error(f"Failed to load cron store: {e}")
            self._jobs = {}
            self._loaded = True
    
    def save(self) -> None:
        """Save jobs to disk with atomic write."""
        self._ensure_dir()
        
        store_data = {
            "version": 1,
            "jobs": [job.to_dict() for job in self._jobs.values()]
        }
        
        # Atomic write: write to temp file then rename
        tmp_path = self.store_path.with_suffix(f".{os.getpid()}.tmp")
        
        try:
            with open(tmp_path, 'w') as f:
                json.dump(store_data, f, indent=2)
            
            # Atomic rename
            tmp_path.rename(self.store_path)
            
            # Best-effort backup
            try:
                backup_path = self.store_path.with_suffix(".json.bak")
                if self.store_path.exists():
                    import shutil
                    shutil.copy2(self.store_path, backup_path)
            except Exception:
                pass
            
            logger.debug(f"Saved {len(self._jobs)} cron jobs to {self.store_path}")
            
        except Exception as e:
            logger.error(f"Failed to save cron store: {e}")
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    def _ensure_loaded(self) -> None:
        """Ensure store is loaded."""
        if not self._loaded:
            self.load()
    
    def add_job(self, job: CronJob) -> None:
        """Add a job to the store."""
        self._ensure_loaded()
        self._jobs[job.id] = job
        self.save()
    
    def get_job(self, job_id: str) -> Optional[CronJob]:
        """Get a job by ID."""
        self._ensure_loaded()
        return self._jobs.get(job_id)
    
    def update_job(self, job: CronJob) -> None:
        """Update an existing job."""
        self._ensure_loaded()
        if job.id in self._jobs:
            self._jobs[job.id] = job
            self.save()
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID. Returns True if removed."""
        self._ensure_loaded()
        if job_id in self._jobs:
            del self._jobs[job_id]
            self.save()
            return True
        return False
    
    def list_jobs(self) -> List[CronJob]:
        """List all jobs."""
        self._ensure_loaded()
        return list(self._jobs.values())
    
    def list_enabled_jobs(self) -> List[CronJob]:
        """List all enabled jobs."""
        self._ensure_loaded()
        return [job for job in self._jobs.values() if job.enabled]
    
    def clear(self) -> None:
        """Remove all jobs."""
        self._jobs = {}
        self.save()
