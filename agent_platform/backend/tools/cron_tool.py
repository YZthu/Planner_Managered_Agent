"""
Cron Tool
Tool for agents to schedule recurring tasks.
"""
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseTool, ToolResult


class CronTool(BaseTool):
    """Schedule and manage recurring tasks."""
    
    @property
    def name(self) -> str:
        return "schedule_task"
    
    @property
    def description(self) -> str:
        return """Schedule a recurring task to run at specified times.

Use this to set up automated recurring tasks like:
- Daily summaries
- Hourly checks
- Weekly reports

Cron expressions:
- Standard: "0 9 * * *" (at 9am daily)
- Simple: "@hourly", "@daily", "@weekly"
- Intervals: "@every 5m", "@every 1h"

Actions: create, list, delete, enable, disable"""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "delete", "enable", "disable"],
                    "description": "Action to perform"
                },
                "expression": {
                    "type": "string",
                    "description": "Cron expression (for create action)"
                },
                "task": {
                    "type": "string",
                    "description": "Task description/prompt (for create action)"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for delete/enable/disable actions)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        expression: Optional[str] = None,
        task: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Execute cron action."""
        try:
            from ..core.cron import get_scheduler, validate_cron_expression
            
            scheduler = get_scheduler()
            
            if action == "create":
                return await self._create_job(scheduler, expression, task)
            elif action == "list":
                return await self._list_jobs(scheduler)
            elif action == "delete":
                return await self._delete_job(scheduler, job_id)
            elif action == "enable":
                return await self._enable_job(scheduler, job_id)
            elif action == "disable":
                return await self._disable_job(scheduler, job_id)
            else:
                return ToolResult(
                    success=False,
                    output=f"Unknown action: {action}",
                    data={"error": "invalid_action"}
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Cron operation failed: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _create_job(self, scheduler, expression: Optional[str], task: Optional[str]) -> ToolResult:
        """Create a new cron job."""
        if not expression:
            return ToolResult(
                success=False,
                output="Missing 'expression' parameter",
                data={"error": "missing_expression"}
            )
        
        if not task:
            return ToolResult(
                success=False,
                output="Missing 'task' parameter",
                data={"error": "missing_task"}
            )
        
        from ..core.cron import validate_cron_expression
        
        if not validate_cron_expression(expression):
            return ToolResult(
                success=False,
                output=f"Invalid cron expression: {expression}",
                data={"error": "invalid_expression"}
            )
        
        job = scheduler.add_job(expression, task)
        
        if job:
            next_run = datetime.fromtimestamp(job.next_run).strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "unknown"
            return ToolResult(
                success=True,
                output=f"Created scheduled task '{job.id}'\nExpression: {expression}\nNext run: {next_run}",
                data={
                    "job_id": job.id,
                    "expression": expression,
                    "task": task,
                    "next_run": next_run
                }
            )
        else:
            return ToolResult(
                success=False,
                output="Failed to create scheduled task",
                data={"error": "creation_failed"}
            )
    
    async def _list_jobs(self, scheduler) -> ToolResult:
        """List all cron jobs."""
        jobs = scheduler.list_jobs()
        
        if not jobs:
            return ToolResult(
                success=True,
                output="No scheduled tasks found.",
                data={"jobs": []}
            )
        
        lines = ["Scheduled Tasks:", ""]
        job_data = []
        
        for job in jobs:
            next_run = datetime.fromtimestamp(job.next_run).strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "N/A"
            status = "✓ Enabled" if job.enabled else "✗ Disabled"
            
            lines.append(f"**{job.id}** [{status}]")
            lines.append(f"  Expression: {job.expression}")
            lines.append(f"  Task: {job.task[:60]}{'...' if len(job.task) > 60 else ''}")
            lines.append(f"  Next run: {next_run}")
            lines.append(f"  Run count: {job.run_count}")
            lines.append("")
            
            job_data.append({
                "id": job.id,
                "expression": job.expression,
                "task": job.task,
                "enabled": job.enabled,
                "next_run": next_run,
                "run_count": job.run_count
            })
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"jobs": job_data}
        )
    
    async def _delete_job(self, scheduler, job_id: Optional[str]) -> ToolResult:
        """Delete a cron job."""
        if not job_id:
            return ToolResult(
                success=False,
                output="Missing 'job_id' parameter",
                data={"error": "missing_job_id"}
            )
        
        if scheduler.remove_job(job_id):
            return ToolResult(
                success=True,
                output=f"Deleted scheduled task '{job_id}'",
                data={"job_id": job_id, "deleted": True}
            )
        else:
            return ToolResult(
                success=False,
                output=f"Task '{job_id}' not found",
                data={"error": "job_not_found"}
            )
    
    async def _enable_job(self, scheduler, job_id: Optional[str]) -> ToolResult:
        """Enable a cron job."""
        if not job_id:
            return ToolResult(
                success=False,
                output="Missing 'job_id' parameter",
                data={"error": "missing_job_id"}
            )
        
        if scheduler.enable_job(job_id):
            return ToolResult(
                success=True,
                output=f"Enabled scheduled task '{job_id}'",
                data={"job_id": job_id, "enabled": True}
            )
        else:
            return ToolResult(
                success=False,
                output=f"Task '{job_id}' not found",
                data={"error": "job_not_found"}
            )
    
    async def _disable_job(self, scheduler, job_id: Optional[str]) -> ToolResult:
        """Disable a cron job."""
        if not job_id:
            return ToolResult(
                success=False,
                output="Missing 'job_id' parameter",
                data={"error": "missing_job_id"}
            )
        
        if scheduler.disable_job(job_id):
            return ToolResult(
                success=True,
                output=f"Disabled scheduled task '{job_id}'",
                data={"job_id": job_id, "enabled": False}
            )
        else:
            return ToolResult(
                success=False,
                output=f"Task '{job_id}' not found",
                data={"error": "job_not_found"}
            )
