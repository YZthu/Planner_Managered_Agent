"""
Concurrency Queue
Lane-based concurrency control for subagent execution.
Inspired by OpenClaw's lanes.ts
"""
import asyncio
from typing import Callable, Awaitable, Any, Dict, Optional
from dataclasses import dataclass, field
from collections import deque

from ..config import config


@dataclass
class QueueItem:
    """Item in the queue"""
    task_id: str
    coroutine: Callable[[], Awaitable[Any]]
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())


class ConcurrencyQueue:
    """
    Lane-based concurrency queue.
    Limits the number of concurrent subagent executions.
    """
    
    def __init__(self, max_concurrent: Optional[int] = None):
        self.max_concurrent = max_concurrent or config.agent.max_concurrent_subagents
        self._queue: deque[QueueItem] = deque()
        self._running: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._processing = False
    
    @property
    def active_count(self) -> int:
        """Number of currently running tasks"""
        return len(self._running)
    
    @property
    def queued_count(self) -> int:
        """Number of tasks waiting in queue"""
        return len(self._queue)
    
    async def enqueue(
        self, 
        task_id: str, 
        coroutine: Callable[[], Awaitable[Any]]
    ) -> asyncio.Future:
        """
        Enqueue a task for execution.
        Returns a future that resolves when the task completes.
        """
        loop = asyncio.get_event_loop()
        item = QueueItem(
            task_id=task_id,
            coroutine=coroutine,
            future=loop.create_future()
        )
        
        async with self._lock:
            self._queue.append(item)
        
        # Start processing if not already running
        if not self._processing:
            asyncio.create_task(self._process_queue())
        
        return item.future
    
    async def _process_queue(self):
        """Process items in the queue"""
        self._processing = True
        
        try:
            while True:
                async with self._lock:
                    # Check if we can start more tasks
                    if len(self._running) >= self.max_concurrent:
                        break
                    
                    if not self._queue:
                        break
                    
                    item = self._queue.popleft()
                
                # Start the task
                task = asyncio.create_task(self._run_item(item))
                self._running[item.task_id] = task
                
        finally:
            self._processing = False
    
    async def _run_item(self, item: QueueItem):
        """Run a single queue item"""
        try:
            result = await item.coroutine()
            if not item.future.done():
                item.future.set_result(result)
        except Exception as e:
            if not item.future.done():
                item.future.set_exception(e)
        finally:
            async with self._lock:
                self._running.pop(item.task_id, None)
            
            # Try to process more items
            if self._queue and not self._processing:
                asyncio.create_task(self._process_queue())
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or running task"""
        async with self._lock:
            # Check if in queue
            for item in self._queue:
                if item.task_id == task_id:
                    self._queue.remove(item)
                    if not item.future.done():
                        item.future.cancel()
                    return True
            
            # Check if running
            if task_id in self._running:
                self._running[task_id].cancel()
                return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status"""
        return {
            "max_concurrent": self.max_concurrent,
            "active": self.active_count,
            "queued": self.queued_count,
            "running_ids": list(self._running.keys()),
        }


# Global queue instance
subagent_queue = ConcurrencyQueue()
