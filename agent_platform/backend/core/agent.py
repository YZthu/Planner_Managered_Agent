"""
Agent Executor
Main agent loop that processes messages and executes tools.
Implements the LLM-as-Planner pattern.
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .registry import registry, SubAgentRun, RunStatus
from .queue import subagent_queue
from .plugins import plugin_registry
from .agent_trace import create_session, configure_tracer
from ..providers.base import BaseLLMProvider, Message, Role, ToolDefinition, LLMResponse
from ..providers.gemini import GeminiProvider
from ..providers import create_deepseek_provider, create_openai_provider
from ..tools.base import BaseTool, ToolResult
from ..tools.spawn_subagent import SpawnSubAgentTool
from ..tools.web_search import WebSearchTool
from ..config import config
from ..prompts import (
    DEFAULT_SYSTEM_PROMPT,
    SUBAGENT_SYSTEM_PROMPT
)
from backend.core.logging import agent_logger


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
        session_id: str = "default",
        role: str = None
    ):
        self.provider = provider or self._create_default_provider()
        # Load default system prompt from config
        self.system_prompt = system_prompt or self._load_system_prompt(
            "subagent" if is_subagent else "default"
        )
        self.is_subagent = is_subagent
        self.session_id = session_id
        # Default role from config if not provided
        self.role = role or config.security.default_role
        
        # Setup tools
        if tools is None:
            tools = self._create_default_tools()
        
        # Filter out spawn_subagent for subagents (prevent recursion)
        if is_subagent:
            tools = [t for t in tools if t.name != "spawn_subagent"]
        
        self.tools = {tool.name: tool for tool in tools}
        self._message_history: List[Message] = []
        self._on_event: Optional[Callable] = None
        
        # Initialize trace session
        self._trace_session = create_session(
            session_id=session_id,
            metadata={"is_subagent": is_subagent, "role": self.role}
        )
        self._session_started = False
        self.logger = agent_logger()
    
    def _load_system_prompt(self, persona_name: str) -> str:
        """Load system prompt from backend.personas module"""
        from ..personas import get_persona_prompt
        return get_persona_prompt(persona_name)

    def set_persona(self, persona: str) -> bool:
        """
        Set the agent's persona (system prompt).
        
        Validates that the persona's requirements are satisfied before switching.
        Falls back to 'default' persona if requirements are not met.
        
        Args:
            persona: Name of the persona to switch to.
        
        Returns:
            True if the requested persona was set, False if fell back to default.
        """
        from ..personas import validate_persona_with_registry
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Validate persona requirements
        result = validate_persona_with_registry(persona)
        
        if result.eligible:
            self.system_prompt = self._load_system_prompt(persona)
            return True
        else:
            # Log warning and fallback to default
            logger.warning(
                f"Persona '{persona}' requirements not satisfied. "
                f"Missing plugins: {result.missing_plugins}, "
                f"Missing core_tools: {result.missing_core_tools}, "
                f"Missing plugin_tools: {result.missing_plugin_tools}. "
                f"Falling back to 'default' persona."
            )
            self.system_prompt = self._load_system_prompt("default")
            return False
            
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
        
        # Start trace session on first turn
        if not self._session_started:
            self._trace_session.start_session(metadata={"provider": self.provider.__class__.__name__})
            self._session_started = True
        
        # Start turn tracing
        self._trace_session.start_turn(user_message)
        
        # Trigger on_agent_start hook
        await plugin_registry.trigger_hook("on_agent_start", user_message=user_message, session_id=self.session_id)
        
        # Context Windowing: Keep only the last N messages
        if len(self._message_history) > config.agent.max_history_messages:
            self._message_history = self._message_history[-config.agent.max_history_messages:]

        # Build messages
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            *self._message_history
        ]
        
        await self._emit_event("thinking", {"status": "Processing your message..."})
        
        self.logger.info(f"Session {self.session_id} - Processing message: {user_message[:200]}...")
        
        iteration = 0
        final_response = ""
        
        while iteration < max_iterations:
            iteration += 1
            
            # Trace LLM request
            tool_names = [t.name for t in self.tools.values()] if self.tools else None
            self._trace_session.log_llm_request(
                model=self.provider.__class__.__name__,
                messages=[{"role": m.role.value, "content": m.content[:500] if m.content else ""} for m in messages[-5:]],
                tools=tool_names
            )
            
            # Call LLM
            llm_start = time.time()
            response = await self.provider.generate(
                messages=messages,
                tools=self.get_tool_definitions() if self.tools else None
            )
            llm_duration = (time.time() - llm_start) * 1000
            
            # Trace LLM response
            self._trace_session.log_llm_response(
                model=self.provider.__class__.__name__,
                content=response.content or "",
                tool_calls=[{"name": tc.name, "args": tc.arguments} for tc in response.tool_calls] if response.tool_calls else None,
                duration_ms=llm_duration
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
                    
                    self.logger.info(f"Tool '{tool_call.name}' executed. Success: {result.success}")
                    
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
        
        # End turn tracing
        self._trace_session.end_turn(final_response)
        
        await self._emit_event("complete", {"response": final_response})
        
        # Trigger on_agent_finish hook
        await plugin_registry.trigger_hook("on_agent_finish", 
            response=final_response, 
            history=self._message_history, 
            session_id=self.session_id
        )
        
        self.logger.info(f"Session {self.session_id} - Finished. Response: {final_response[:200]}...")
        
        return final_response
    
    async def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name"""
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output=f"Unknown tool: {name}"
            )
        
        # Check Permissions
        from ..security.access_control import access_control
        if not access_control.check_permission(self.role, name):
            return ToolResult(
                success=False,
                output=f"Permission Denied: Role '{self.role}' cannot use tool '{name}'"
            )

        # Trigger on_tool_start
        await plugin_registry.trigger_hook("on_tool_start", name=name, arguments=arguments, session_id=self.session_id)
        
        try:
            try:
                # Add session_id for spawn_subagent
                if name == "spawn_subagent":
                    arguments["session_id"] = self.session_id
                
                # Trace tool call
                self._trace_session.log_tool_call(name, arguments)
                tool_start = time.time()
                
                # Robust execution with timeout
                result = await asyncio.wait_for(
                    tool.execute(**arguments),
                    timeout=config.agent.subagent_timeout_seconds
                )
                tool_duration = (time.time() - tool_start) * 1000
                
                # Trace tool result
                self._trace_session.log_tool_result(
                    tool_name=name,
                    success=result.success,
                    result=result.output[:1000] if result.output else None,
                    duration_ms=tool_duration
                )
                
                # Trigger on_tool_end (success)
                await plugin_registry.trigger_hook("on_tool_end", name=name, result=result, session_id=self.session_id)
                
                self.logger.info(f"Tool '{name}' completed successfully ({tool_duration:.2f}ms)")
                
                return result
            except asyncio.TimeoutError:
                return ToolResult(
                    success=False,
                    output=f"Tool execution timed out after {config.agent.subagent_timeout_seconds}s"
                )
        except Exception as e:
            # Trace tool error
            self._trace_session.log_tool_result(
                tool_name=name,
                success=False,
                error=str(e)
            )
            
            # Trigger on_error
            await plugin_registry.trigger_hook("on_error", error=e, context=f"tool:{name}", session_id=self.session_id)
            
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
        # Start trace turn (use registry run_id in metadata)
        self._trace_session.start_turn(
            user_input=task,
            metadata={"subagent_run_id": run_id}
        )
        
        # Simple single-turn execution for subagent
        messages = [
            Message(role=Role.SYSTEM, content=self.system_prompt),
            Message(role=Role.USER, content=f"Your task: {task}\n\nComplete this task now.")
        ]
        
        # Allow web search for subagents
        # Note: If we wanted to use other tools, we'd need to configure them here
        tools = [WebSearchTool()]
        
        max_iterations = 5
        final_result = "Task completed (max iterations reached)."
        
        for _ in range(max_iterations):
            # Trace LLM request
            self._trace_session.log_llm_request(
                model=self.provider.__class__.__name__,
                messages=[{"role": m.role.value, "content": m.content[:500] if m.content else ""} for m in messages[-3:]],
                tools=[t.name for t in tools]
            )
            
            # Call LLM
            llm_start = time.time()
            response = await self.provider.generate(
                messages=messages,
                tools=[ToolDefinition(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters
                ) for t in tools]
            )
            llm_duration = (time.time() - llm_start) * 1000
            
            # Trace LLM response
            self._trace_session.log_llm_response(
                model=self.provider.__class__.__name__,
                content=response.content or "",
                tool_calls=[{"name": tc.name, "args": tc.arguments} for tc in response.tool_calls] if response.tool_calls else None,
                duration_ms=llm_duration
            )
            
            if response.tool_calls:
                messages.append(Message(
                    role=Role.ASSISTANT,
                    content=response.content or ""
                ))
                
                for tc in response.tool_calls:
                    tool = next((t for t in tools if t.name == tc.name), None)
                    if tool:
                        # Trace tool call
                        self._trace_session.log_tool_call(tc.name, tc.arguments)
                        tool_start = time.time()
                        
                        try:
                            # Execute tool
                            result = await tool.execute(**tc.arguments)
                            tool_duration = (time.time() - tool_start) * 1000
                            
                            # Trace tool result
                            self._trace_session.log_tool_result(
                                tool_name=tc.name,
                                success=result.success,
                                result=result.output[:1000] if result.output else None,
                                duration_ms=tool_duration
                            )
                            
                            messages.append(Message(
                                role=Role.TOOL,
                                content=result.output,
                                tool_call_id=tc.id,
                                name=tc.name
                            ))
                        except Exception as e:
                            # Trace tool error
                            self._trace_session.log_tool_result(
                                tool_name=tc.name,
                                success=False,
                                error=str(e)
                            )
                            messages.append(Message(
                                role=Role.TOOL,
                                content=f"Error: {str(e)}",
                                tool_call_id=tc.id,
                                name=tc.name
                            ))
            else:
                final_result = response.content or "Task completed but no response generated."
                break
        
        # End trace turn
        self._trace_session.end_turn(final_result)
        
        return final_result
    
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
