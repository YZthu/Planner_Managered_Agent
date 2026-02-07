"""
Spawn SubAgent Tool
Core orchestration tool for spawning isolated subagents.
Inspired by OpenClaw's sessions_spawn tool.
"""
from typing import Dict, Any, Optional
import asyncio

from .base import BaseTool, ToolResult
from ..core.registry import registry, SubAgentRun, RunStatus
from ..core.queue import subagent_queue


class SpawnSubAgentTool(BaseTool):
    """
    Spawn a background subagent for a specific task.
    
    The subagent runs in isolation and reports results back
    when complete. Use this to parallelize work.
    """
    
    def __init__(self):
        """
        Initialize without factory. 
        AgentExecutor is lazily loaded to avoid circular imports.
        """
        pass
    
    @property
    def name(self) -> str:
        return "spawn_subagent"
    
    @property
    def description(self) -> str:
        return """Spawn a background subagent to handle a specific task.

The subagent runs independently and its result will be announced when complete.
Use this to parallelize work - spawn multiple subagents for different subtasks.

Returns immediately with a run_id that can be used to track status.
The subagent's result will be automatically sent back to you when complete."""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The specific task for the subagent to complete. Be clear and detailed."
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for this subagent (e.g., 'research_news', 'extract_data')"
                }
            },
            "required": ["task"]
        }
    
    async def execute(
        self,
        task: str,
        label: Optional[str] = None,
        session_id: str = "default",
        **kwargs
    ) -> ToolResult:
        """Spawn a subagent for the given task"""
        # Create run record
        run = SubAgentRun(
            parent_session_id=session_id,
            task=task,
            label=label or task[:50],
            status=RunStatus.PENDING
        )
        
        # Register the run
        await registry.register(run)
        
        # Queue the subagent execution
        async def run_subagent():
            try:
                # Update status to running
                await registry.update_status(run.run_id, RunStatus.RUNNING)
                
                # Lazy import AgentExecutor to avoid circular dependency
                from ..core.agent import AgentExecutor
                
                # Create independent runner
                # Note: Uses default provider from config
                runner = AgentExecutor(
                    is_subagent=True,
                    session_id=session_id
                )
                
                result = await runner.run_subagent(task, run.run_id)
                
                # Update with result
                await registry.update_status(
                    run.run_id, 
                    RunStatus.COMPLETED,
                    result=result
                )
                return result
            except asyncio.TimeoutError:
                await registry.update_status(
                    run.run_id,
                    RunStatus.TIMEOUT,
                    error="Subagent execution timed out"
                )
            except Exception as e:
                await registry.update_status(
                    run.run_id,
                    RunStatus.ERROR,
                    error=str(e)
                )
            
        # Enqueue the subagent
        asyncio.create_task(subagent_queue.enqueue(run.run_id, run_subagent))
        
        return ToolResult(
            success=True,
            output=f"Subagent spawned successfully. Run ID: {run.run_id}. Label: {run.label}. The result will be announced when complete.",
            data={
                "status": "accepted",
                "run_id": run.run_id,
                "label": run.label
            }
        )
