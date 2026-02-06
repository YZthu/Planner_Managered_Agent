"""
OpenAI-Compatible LLM Provider
A unified provider for any API following the OpenAI format.
Supports: OpenAI, DeepSeek, Ollama, vLLM, Azure OpenAI, etc.
"""
import json
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI

from .base import BaseLLMProvider, Message, LLMResponse, ToolCall, ToolDefinition, Role
from ..config import config


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Unified provider for OpenAI-compatible APIs.
    
    Works with any API that follows the OpenAI chat completions format:
    - OpenAI (api.openai.com)
    - DeepSeek (api.deepseek.com)
    - Ollama (localhost:11434/v1)
    - vLLM (your-vllm-server/v1)
    - Azure OpenAI
    - And more...
    """
    
    def __init__(
        self,
        provider_name: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        Initialize the OpenAI-compatible provider.
        
        Args:
            provider_name: Name identifier for this provider (e.g., "openai", "deepseek")
            model: Model identifier (e.g., "gpt-4o-mini", "deepseek-chat")
            api_key: API key for authentication
            base_url: Base URL for the API (None for OpenAI default)
            temperature: Default temperature for generation
            max_tokens: Default max tokens for generation
        """
        self._name = provider_name
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._default_temperature = temperature
        self._default_max_tokens = max_tokens
        
        if not self._api_key:
            raise ValueError(f"{provider_name} API key not configured")
        
        # Create client with optional base_url
        client_kwargs = {"api_key": self._api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            
        self._client = AsyncOpenAI(**client_kwargs)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def model(self) -> str:
        return self._model
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to OpenAI format"""
        result = []
        for msg in messages:
            message_dict = {
                "role": msg.role.value,
                "content": msg.content
            }
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                message_dict["name"] = msg.name
            # Include tool_calls for assistant messages
            if msg.role == Role.ASSISTANT and msg.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            result.append(message_dict)
        return result
    
    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert tool definitions to OpenAI format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in tools
        ]
    
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate response using OpenAI-compatible API"""
        openai_messages = self._convert_messages(messages)
        
        kwargs = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._default_max_tokens,
        }
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"
        
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(
                content=f"Error calling {self._name} API: {str(e)}",
                finish_reason="error"
            )
        
        # Extract response
        choice = response.choices[0]
        message = choice.message
        
        content = message.content
        tool_calls = []
        
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": tc.function.arguments}
                
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments
                ))
        
        finish_reason = choice.finish_reason or "stop"
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }
        )


# Factory functions for common providers

def create_openai_provider(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAICompatibleProvider:
    """Create an OpenAI provider instance"""
    return OpenAICompatibleProvider(
        provider_name="openai",
        model=model or config.llm.openai_model,
        api_key=api_key or config.llm.openai_api_key,
        base_url=None,  # Use default OpenAI URL
        temperature=config.llm.openai.temperature,
        max_tokens=config.llm.openai.max_tokens,
    )


def create_deepseek_provider(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAICompatibleProvider:
    """Create a DeepSeek provider instance"""
    return OpenAICompatibleProvider(
        provider_name="deepseek",
        model=model or config.llm.deepseek_model,
        api_key=api_key or config.llm.deepseek_api_key,
        base_url=config.llm.deepseek_base_url,
        temperature=config.llm.deepseek.temperature,
        max_tokens=config.llm.deepseek.max_tokens,
    )


def create_ollama_provider(
    model: str = "llama3",
    base_url: str = "http://localhost:11434/v1",
) -> OpenAICompatibleProvider:
    """Create an Ollama provider instance (local models)"""
    return OpenAICompatibleProvider(
        provider_name="ollama",
        model=model,
        api_key="ollama",  # Ollama doesn't need a real key
        base_url=base_url,
        temperature=0.7,
        max_tokens=4096,
    )
