"""
Base Tool Interface
Abstract base class for all tools.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result from tool execution"""
    success: bool
    output: str
    data: Optional[Dict[str, Any]] = None


class BaseTool(ABC):
    """Abstract base class for tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used in function calling)"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for tool parameters"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments.
        
        Returns:
            ToolResult with success status and output
        """
        pass
    
    def to_definition(self) -> Dict[str, Any]:
        """Convert to tool definition for LLM"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
