"""
SubAgent Registry
Tracks lifecycle of all subagent runs with persistence.
Inspired by OpenClaw's subagent-registry.ts
"""
import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from pydantic import BaseModel, Field
import aiosqlite

from ..config import config


class RunStatus(str, Enum):
    """Status of a subagent run"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


class SubAgentRun(BaseModel):
    """Represents a single subagent run"""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_session_id: str
    task: str
    label: Optional[str] = None
    status: RunStatus = RunStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model: Optional[str] = None
    
    class Config:
        use_enum_values = True


class SubAgentRegistry:
    """
    Registry for tracking subagent runs.
    Provides lifecycle management and persistence.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.data_dir / "registry.db"
        self._runs: Dict[str, SubAgentRun] = {}
        self._listeners: Dict[str, List[Callable]] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the database"""
        if self._initialized:
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS subagent_runs (
                    run_id TEXT PRIMARY KEY,
                    parent_session_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    label TEXT,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    model TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_parent_session 
                ON subagent_runs(parent_session_id)
            """)
            await db.commit()
        
        # Load existing runs
        await self._load_runs()
        self._initialized = True
    
    async def _load_runs(self):
        """Load runs from database"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM subagent_runs WHERE status IN (?, ?)",
                (RunStatus.PENDING.value, RunStatus.RUNNING.value)
            ) as cursor:
                async for row in cursor:
                    run = SubAgentRun(
                        run_id=row["run_id"],
                        parent_session_id=row["parent_session_id"],
                        task=row["task"],
                        label=row["label"],
                        status=RunStatus(row["status"]),
                        result=row["result"],
                        error=row["error"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                        model=row["model"]
                    )
                    self._runs[run.run_id] = run
    
    async def register(self, run: SubAgentRun) -> SubAgentRun:
        """Register a new subagent run"""
        self._runs[run.run_id] = run
        await self._persist(run)
        await self._notify(run.parent_session_id, "registered", run)
        return run
    
    async def update_status(
        self, 
        run_id: str, 
        status: RunStatus,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Optional[SubAgentRun]:
        """Update the status of a run"""
        run = self._runs.get(run_id)
        if not run:
            return None
        
        run.status = status
        if result is not None:
            run.result = result
        if error is not None:
            run.error = error
        
        if status == RunStatus.RUNNING and not run.started_at:
            run.started_at = datetime.now()
        elif status in (RunStatus.COMPLETED, RunStatus.ERROR, RunStatus.TIMEOUT):
            run.completed_at = datetime.now()
        
        await self._persist(run)
        await self._notify(run.parent_session_id, "updated", run)
        return run
    
    def get(self, run_id: str) -> Optional[SubAgentRun]:
        """Get a run by ID"""
        return self._runs.get(run_id)
    
    def list_by_session(self, session_id: str) -> List[SubAgentRun]:
        """List all runs for a session"""
        return [
            run for run in self._runs.values()
            if run.parent_session_id == session_id
        ]
    
    def list_active(self) -> List[SubAgentRun]:
        """List all active (pending/running) runs"""
        return [
            run for run in self._runs.values()
            if run.status in (RunStatus.PENDING, RunStatus.RUNNING)
        ]
    
    async def _persist(self, run: SubAgentRun):
        """Persist run to database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO subagent_runs 
                (run_id, parent_session_id, task, label, status, result, error,
                 created_at, started_at, completed_at, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.parent_session_id,
                run.task,
                run.label,
                run.status.value if isinstance(run.status, RunStatus) else run.status,
                run.result,
                run.error,
                run.created_at.isoformat(),
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                run.model
            ))
            await db.commit()
    
    def add_listener(self, session_id: str, callback: Callable):
        """Add a listener for run updates"""
        if session_id not in self._listeners:
            self._listeners[session_id] = []
        self._listeners[session_id].append(callback)
    
    def remove_listener(self, session_id: str, callback: Callable):
        """Remove a listener"""
        if session_id in self._listeners:
            self._listeners[session_id] = [
                cb for cb in self._listeners[session_id] if cb != callback
            ]
    
    async def _notify(self, session_id: str, event: str, run: SubAgentRun):
        """Notify listeners of run updates"""
        callbacks = self._listeners.get(session_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, run)
                else:
                    callback(event, run)
            except Exception as e:
                print(f"Error in listener callback: {e}")


# Global registry instance
registry = SubAgentRegistry()
