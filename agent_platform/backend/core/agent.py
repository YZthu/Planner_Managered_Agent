"""
Agent Executor
Main agent loop that processes messages and executes tools.
Implements the LLM-as-Planner pattern.
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .registry import registry, SubAgentRun, RunStatus
from .queue import subagent_queue
from .plugins import plugin_registry
from ..providers.base import BaseLLMProvider, Message, Role, ToolDefinition, LLMResponse
from ..providers.gemini import GeminiProvider
from ..providers import create_deepseek_provider, create_openai_provider
from ..tools.base import BaseTool, ToolResult
from ..tools.spawn_subagent import SpawnSubAgentTool
from ..tools.web_search import WebSearchTool
from ..config import config


# Default system prompt for the main agent
DEFAULT_SYSTEM_PROMPT = """You are a powerful AI assistant with the ability to spawn subagents for parallel work.

## Core Capabilities
1. **Direct Response**: Answer questions directly when appropriate
2. **Web Search**: Use the web_search tool to find current information
3. **Task Delegation**: Use spawn_subagent to delegate subtasks for parallel processing

## Guidelines
- For complex tasks, break them down and spawn subagents for parallel execution
- Each subagent works independently on its assigned task
- Subagent results are automatically reported back to you
- Synthesize subagent results into a coherent response for the user

## When to Spawn Subagents
- Research tasks that can be parallelized (e.g., searching different topics)
- Multi-step tasks where steps can run concurrently
- Tasks requiring different types of analysis

## When NOT to Spawn Subagents
- Simple questions you can answer directly
- Tasks that must be sequential
- Single-focus tasks better handled directly

45. **Thinking Process**: You have a "thinking" capability. Use it to plan complex tasks before acting. Wrap your thoughts in <thought> tags.
46. 
47. Be helpful, thorough, and efficient. Leverage subagents to maximize productivity."""


# Subagent system prompt
SUBAGENT_SYSTEM_PROMPT = """You are a focused subagent spawned to complete a specific task.

## Your Role
- Complete ONLY the assigned task
- Be thorough but concise in your response
- Your entire response will be reported back to the main agent

## Rules
1. Stay focused on your specific task
2. Do not try to spawn other subagents
3. Do not ask questions - work with what you have
4. Provide a complete, self-contained response

Complete your task now."""


class AgentExecutor:
    """
    Main agent executor implementing the LLM-as-Planner pattern.
    """
    
    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        is_subagent: bool = False,
        session_id: str = "default"
    ):
        self.provider = provider or self._create_default_provider()
        self.system_prompt = system_prompt or (
            SUBAGENT_SYSTEM_PROMPT if is_subagent else DEFAULT_SYSTEM_PROMPT
        )
        self.is_subagent = is_subagent
        self.session_id = session_id
        
        # Setup tools
        if tools is None:
            tools = self._create_default_tools()
        
        # Filter out spawn_subagent for subagents (prevent recursion)
        if is_subagent:
            tools = [t for t in tools if t.name != "spawn_subagent"]
        
        self.tools = {tool.name: tool for tool in tools}
        self._message_history: List[Message] = []
        self._on_event: Optional[Callable] = None
    
    def _create_default_provider(self, provider_name: str = None) -> BaseLLMProvider:
        """Create LLM provider based on name or config"""
        provider = provider_name or config.llm.default_provider
        
        if provider == "gemini":
            return GeminiProvider()
        elif provider == "deepseek":
            return create_deepseek_provider()
        elif provider == "openai":
            return create_openai_provider()
        else:
            # Fallback to Gemini
            return GeminiProvider()
    
    def set_provider(self, provider_name: str):
        """Switch to a different LLM provider"""
        self.provider = self._create_default_provider(provider_name)
    
    
    def _create_default_tools(self) -> List[BaseTool]:
        """Create default tool set from plugins"""
        tools = plugin_registry.get_all_tools()
        
        # If no tools loaded from plugins (e.g. registry not initialized), 
        # fallback to minimal set or empty.
        # But main.py should initialize plugins.
        return tools
    
    def set_event_handler(self, handler: Callable):
        """Set event handler for streaming updates"""
        self._on_event = handler
    
    async def _emit_event(self, event_type: str, data: Any):
        """Emit an event to the handler"""
        if self._on_event:
            try:
                if asyncio.iscoroutinefunction(self._on_event):
                    await self._on_event(event_type, data)
                else:
                    self._on_event(event_type, data)
            except Exception as e:
                print(f"Error in event handler: {e}")
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get tool definitions for LLM"""
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters
            )
            for tool in self.tools.values()
        ]
    
    async def run(
        self,
        user_message: str,
        max_iterations: int = 10
    ) -> str:
        """
        Run the agent on a user message.
        
        Args:
            user_message: The user's input
            max_iterations: Maximum tool call iterations
        
        Returns:
            The agent's final response
        """
        # Add user message to history
        self._message_history.append(Message(role=Role.USER, content=user_message))
        
        # Context Windowing: Keep only the last N messages
        if len(self._message_history) > config.agent.max_history_messages:
            self._message_history = self._message_history[-config.agent.max_history_messages:]

        # Build messages
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            *self._message_history
        ]
        
        await self._emit_event("thinking", {"status": "Processing your message..."})
        
        iteration = 0
        final_response = ""
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.generate(
                messages=messages,
                tools=self.get_tool_definitions() if self.tools else None
            )

            # Thinking Steps Extraction
            if config.agent.enable_thinking and response.content and "<thought>" in response.content:
                import re
                thoughts = re.findall(r'<thought>(.*?)</thought>', response.content, re.DOTALL)
                for thought in thoughts:
                    await self._emit_event("thinking", {"content": thought.strip()})
                
                # Optional: Remove thoughts from content so user sees only the answer
                # response.content = re.sub(r'<thought>.*?</thought>', '', response.content, flags=re.DOTALL).strip()
            
            # Check for tool calls
            if response.tool_calls:
                await self._emit_event("tool_calls", {
                    "tools": [{"name": tc.name, "args": tc.arguments} for tc in response.tool_calls]
                })
                
                # Add assistant message with tool calls
                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=response.content or "",
                    tool_calls=response.tool_calls  # Include tool_calls for proper message history
                )
                messages.append(assistant_msg)
                
                # Execute each tool
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call.name, tool_call.arguments)
                    
                    await self._emit_event("tool_result", {
                        "name": tool_call.name,
                        "result": result.output[:500]  # Truncate for display
                    })
                    
                    # Add tool result to messages
                    messages.append(Message(
                        role=Role.TOOL,
                        content=result.output,
                        tool_call_id=tool_call.id,
                        name=tool_call.name
                    ))
            
            else:
                # No tool calls, we have the final response
                final_response = response.content or ""
                break
        
        # Add final response to history
        if final_response:
            self._message_history.append(Message(
                role=Role.ASSISTANT,
                content=final_response
            ))
        
        await self._emit_event("complete", {"response": final_response})
        
        return final_response
    
    async def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name"""
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output=f"Unknown tool: {name}"
            )
        
        try:
            try:
                # Add session_id for spawn_subagent
                if name == "spawn_subagent":
                    arguments["session_id"] = self.session_id
                
                # Robust execution with timeout
                return await asyncio.wait_for(
                    tool.execute(**arguments),
                    timeout=config.agent.subagent_timeout_seconds
                )
            except asyncio.TimeoutError:
                return ToolResult(
                    success=False,
                    output=f"Tool execution timed out after {config.agent.subagent_timeout_seconds}s"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Tool execution error: {str(e)}"
            )
    
    async def run_subagent(self, task: str, run_id: str) -> str:
        """
        Run as a subagent for a specific task.
        
        Args:
            task: The task to complete
            run_id: The run ID for tracking
        
        Returns:
            The subagent's response
        """
        # Simple single-turn execution for subagent
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            Message(role=Role.USER, content=f"Your task: {task}\n\nComplete this task now.")
        ]
        
        # Allow web search for subagents
        tools = [WebSearchTool()]
        
        max_iterations = 5
        for _ in range(max_iterations):
            response = await self.provider.generate(
                messages=messages,
                tools=[ToolDefinition(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters
                ) for t in tools]
            )
            
            if response.tool_calls:
                messages.append(Message(
                    role=Role.ASSISTANT,
                    content=response.content or ""
                ))
                
                for tc in response.tool_calls:
                    tool = next((t for t in tools if t.name == tc.name), None)
                    if tool:
                        result = await tool.execute(**tc.arguments)
                        messages.append(Message(
                            role=Role.TOOL,
                            content=result.output,
                            tool_call_id=tc.id,
                            name=tc.name
                        ))
            else:
                return response.content or "Task completed but no response generated."
        
        return "Task completed (max iterations reached)."
    
    def clear_history(self):
        """Clear conversation history"""
        self._message_history.clear()


# Convenience function to get available subagent status
async def get_subagent_status(session_id: str) -> List[Dict[str, Any]]:
    """Get status of all subagents for a session"""
    runs = registry.list_by_session(session_id)
    return [
        {
            "run_id": run.run_id,
            "label": run.label,
            "status": run.status,
            "task": run.task[:100] + "..." if len(run.task) > 100 else run.task,
            "created_at": run.created_at.isoformat(),
            "result": run.result[:200] if run.result else None,
            "error": run.error
        }
        for run in runs
    ]
