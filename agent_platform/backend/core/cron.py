"""
Cron Scheduler
Background scheduler for executing cron jobs.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable, Any
import logging

from .cron_store import CronStore, CronJob

logger = logging.getLogger(__name__)

# Try to import croniter for cron expression parsing
try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
    logger.warning("croniter not installed. Cron scheduling will use simple interval parsing.")


def parse_cron_expression(expression: str) -> Optional[float]:
    """
    Parse a cron expression and return the next run time as Unix timestamp.
    
    Supports:
    - Standard cron: "* * * * *" (min hour dom mon dow)
    - Simple intervals: "@every 5m", "@every 1h", "@hourly", "@daily"
    """
    expression = expression.strip()
    
    # Handle simple interval syntax
    if expression.startswith("@"):
        return _parse_simple_interval(expression)
    
    # Use croniter for standard cron expressions
    if CRONITER_AVAILABLE:
        try:
            cron = croniter(expression, datetime.now())
            next_time = cron.get_next(datetime)
            return next_time.timestamp()
        except Exception as e:
            logger.error(f"Invalid cron expression '{expression}': {e}")
            return None
    else:
        # Fallback: treat as @hourly
        logger.warning(f"croniter not available, treating '{expression}' as hourly")
        return datetime.now().timestamp() + 3600


def _parse_simple_interval(expression: str) -> Optional[float]:
    """Parse simple interval expressions like @every 5m, @hourly, etc."""
    now = datetime.now().timestamp()
    
    if expression == "@hourly":
        return now + 3600
    elif expression == "@daily":
        return now + 86400
    elif expression == "@weekly":
        return now + 604800
    elif expression.startswith("@every "):
        interval_str = expression[7:].strip()
        seconds = _parse_duration(interval_str)
        if seconds:
            return now + seconds
    
    return None


def _parse_duration(duration: str) -> Optional[int]:
    """Parse duration string like '5m', '1h', '30s' to seconds."""
    duration = duration.strip().lower()
    
    if not duration:
        return None
    
    unit = duration[-1]
    try:
        value = int(duration[:-1])
    except ValueError:
        return None
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
    }
    
    return value * multipliers.get(unit, 1)


def calculate_next_run(expression: str, from_time: Optional[datetime] = None) -> Optional[float]:
    """Calculate the next run time for a cron expression."""
    if from_time is None:
        from_time = datetime.now()
    
    expression = expression.strip()
    
    if expression.startswith("@"):
        return _parse_simple_interval(expression)
    
    if CRONITER_AVAILABLE:
        try:
            cron = croniter(expression, from_time)
            next_time = cron.get_next(datetime)
            return next_time.timestamp()
        except Exception as e:
            logger.error(f"Invalid cron expression '{expression}': {e}")
            return None
    
    return None


def validate_cron_expression(expression: str) -> bool:
    """Validate a cron expression."""
    expression = expression.strip()
    
    # Simple intervals are always valid
    if expression in ["@hourly", "@daily", "@weekly"]:
        return True
    
    if expression.startswith("@every "):
        duration = expression[7:].strip()
        return _parse_duration(duration) is not None
    
    # Use croniter for standard cron validation
    if CRONITER_AVAILABLE:
        try:
            croniter(expression)
            return True
        except Exception:
            return False
    
    # Without croniter, accept any expression
    return True


class CronScheduler:
    """Background scheduler for cron jobs."""
    
    def __init__(
        self,
        store: Optional[CronStore] = None,
        executor: Optional[Callable[[str, str], Awaitable[Any]]] = None
    ):
        """
        Initialize the scheduler.
        
        Args:
            store: CronStore for job persistence
            executor: Async function to execute jobs: (task, session_id) -> result
        """
        self.store = store or CronStore()
        self.executor = executor
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 60  # Check every minute
    
    def set_executor(self, executor: Callable[[str, str], Awaitable[Any]]) -> None:
        """Set the executor function for running jobs."""
        self.executor = executor
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self.store.load()
        
        # Update next_run for all jobs
        for job in self.store.list_jobs():
            if job.next_run is None or job.next_run < datetime.now().timestamp():
                job.next_run = calculate_next_run(job.expression)
                self.store.update_job(job)
        
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Cron scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cron scheduler stopped")
    
    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cron scheduler loop: {e}")
                await asyncio.sleep(self._check_interval)
    
    async def _check_and_run_jobs(self) -> None:
        """Check for due jobs and run them."""
        now = datetime.now().timestamp()
        
        for job in self.store.list_enabled_jobs():
            if job.next_run and job.next_run <= now:
                await self._run_job(job)
    
    async def _run_job(self, job: CronJob) -> None:
        """Execute a single job."""
        logger.info(f"Running cron job {job.id}: {job.task[:50]}...")
        
        try:
            if self.executor:
                await self.executor(job.task, job.session_id or "cron")
            
            # Update job after execution
            job.last_run = datetime.now().timestamp()
            job.run_count += 1
            job.next_run = calculate_next_run(job.expression)
            self.store.update_job(job)
            
            logger.info(f"Cron job {job.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Cron job {job.id} failed: {e}")
            # Still update next_run so we don't retry immediately
            job.next_run = calculate_next_run(job.expression)
            self.store.update_job(job)
    
    def add_job(
        self,
        expression: str,
        task: str,
        job_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[CronJob]:
        """
        Add a new cron job.
        
        Args:
            expression: Cron expression (e.g., "0 9 * * *" or "@every 1h")
            task: Task description/prompt to execute
            job_id: Optional job ID (auto-generated if not provided)
            session_id: Optional session to run in
            metadata: Optional metadata
        
        Returns:
            Created CronJob or None if expression is invalid
        """
        if not validate_cron_expression(expression):
            logger.error(f"Invalid cron expression: {expression}")
            return None
        
        job = CronJob(
            id=job_id or str(uuid.uuid4())[:8],
            expression=expression,
            task=task,
            session_id=session_id,
            metadata=metadata or {},
            next_run=calculate_next_run(expression)
        )
        
        self.store.add_job(job)
        logger.info(f"Added cron job {job.id}: {expression}")
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        removed = self.store.remove_job(job_id)
        if removed:
            logger.info(f"Removed cron job {job_id}")
        return removed
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        job = self.store.get_job(job_id)
        if job:
            job.enabled = True
            job.next_run = calculate_next_run(job.expression)
            self.store.update_job(job)
            return True
        return False
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        job = self.store.get_job(job_id)
        if job:
            job.enabled = False
            self.store.update_job(job)
            return True
        return False
    
    def list_jobs(self) -> list:
        """List all jobs."""
        return self.store.list_jobs()
    
    def get_job(self, job_id: str) -> Optional[CronJob]:
        """Get a job by ID."""
        return self.store.get_job(job_id)


# Global scheduler instance
_scheduler: Optional[CronScheduler] = None


def get_scheduler() -> CronScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        from ..config import config
        store_path = getattr(config, 'cron', None)
        if store_path and hasattr(store_path, 'store_path'):
            _scheduler = CronScheduler(CronStore(store_path.store_path))
        else:
            _scheduler = CronScheduler()
    return _scheduler
