"""
Base LLM Provider Interface
Abstract base class for all LLM providers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class Role(str, Enum):
    """Message roles"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """Chat message"""
    role: Role
    content: str
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool responses
    tool_calls: Optional[List["ToolCall"]] = None  # For assistant messages with tool calls


class ToolCall(BaseModel):
    """Tool call from LLM"""
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    """Response from LLM"""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = []
    finish_reason: str = "stop"
    usage: Dict[str, int] = {}


class ToolDefinition(BaseModel):
    """Tool definition for LLM"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier"""
        pass
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: Conversation history
            tools: Available tools for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            LLMResponse with content and/or tool calls
        """
        pass
    
    def format_system_prompt(self, base_prompt: str, skills_prompt: str = "") -> str:
        """Format complete system prompt with skills"""
        parts = [base_prompt]
        if skills_prompt:
            parts.append("\n\n# Available Skills\n" + skills_prompt)
        return "\n".join(parts)
