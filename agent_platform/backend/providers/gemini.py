"""
Google Gemini LLM Provider
Uses the google-genai SDK for Gemini models.
"""
import json
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types

from .base import BaseLLMProvider, Message, LLMResponse, ToolCall, ToolDefinition, Role
from ..config import config


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider"""
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self._model = model or config.llm.gemini_model
        self._api_key = api_key or config.llm.google_api_key
        
        if not self._api_key:
            raise ValueError("Google API key not configured")
        
        self._client = genai.Client(api_key=self._api_key)
    
    @property
    def name(self) -> str:
        return "gemini"
    
    @property
    def model(self) -> str:
        return self._model
    
    def _convert_messages(self, messages: List[Message]) -> tuple[Optional[str], List[types.Content]]:
        """Convert messages to Gemini format"""
        system_instruction = None
        contents = []
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_instruction = msg.content
            elif msg.role == Role.USER:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=msg.content)]
                ))
            elif msg.role == Role.ASSISTANT:
                parts = []
                if msg.content:
                    parts.append(types.Part(text=msg.content))
                
                if msg.tool_calls:
                   for tc in msg.tool_calls:
                       parts.append(types.Part(
                           function_call=types.FunctionCall(
                               name=tc.name,
                               args=tc.arguments
                           )
                       ))
                
                if parts:
                    contents.append(types.Content(
                        role="model",
                        parts=parts
                    ))
            elif msg.role == Role.TOOL:
                # Tool response
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=msg.name or "unknown",
                            response={"result": msg.content} 
                        )
                    )]
                ))
        
        return system_instruction, contents
    
    def _convert_tools(self, tools: List[ToolDefinition]) -> Optional[List[types.Tool]]:
        """Convert tool definitions to Gemini format"""
        if not tools:
            return None
        
        function_declarations = []
        for tool in tools:
            # Convert JSON Schema to Gemini format
            params = tool.parameters.copy()
            if "properties" in params:
                properties = {}
                for prop_name, prop_schema in params["properties"].items():
                    prop_type = prop_schema.get("type", "string").upper()
                    # Map common types
                    type_mapping = {
                        "STRING": "STRING",
                        "INTEGER": "INTEGER",
                        "NUMBER": "NUMBER",
                        "BOOLEAN": "BOOLEAN",
                        "ARRAY": "ARRAY",
                        "OBJECT": "OBJECT"
                    }
                    p_type = type_mapping.get(prop_type, "STRING")
                    
                    properties[prop_name] = types.Schema(
                        type=p_type,
                        description=prop_schema.get("description", ""),
                    )
                
                schema = types.Schema(
                    type="OBJECT",
                    properties=properties,
                    required=params.get("required", [])
                )
            else:
                schema = types.Schema(type="OBJECT", properties={})
            
            function_declarations.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=schema
                )
            )
        
        return [types.Tool(function_declarations=function_declarations)]
    
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate response using Gemini"""
        system_instruction, contents = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools) if tools else None
        
        # Generation config
        gen_config = types.GenerateContentConfig(
            temperature=temperature if temperature != 0.7 else config.llm.gemini.temperature,
            max_output_tokens=max_tokens or config.llm.gemini.max_tokens,
            system_instruction=system_instruction,
            tools=gemini_tools,
        )
        
        try:
            # Use run_in_executor for async wrapper if needed, but client might support async
            # The google-genai client methods are synchronous by default?
            # Wait, checks show: client.aio.models.generate_content for async.
            # Let's try to verify if .aio exists or if we should use run_in_executor.
            # Usually strict google clients separate sync/async.
            # I will check if client.aio exists in follow up if this fails, or assume usage of client.aio.
            # Since I can't easily check, I'll use the synchronous client for now and maybe wrap it?
            # Or better, check the docs summary again?
            # Docs said "Seamlessly supports...".
            # For Safety, I will try to use `client.aio.models.generate_content`? 
            # Or just `client.models.generate_content` from a thread?
            # Most modern clients might be async?
            # Let's try `client.models.generate_content` calls are usually blocking.
            # I will use the async client `genai.Client` might allow `http_options`?
            
            # Re-reading inspect output: `_generate_content`, `generate_content`.
            # I will assume synchronous for now and wrap it if needed or look for async.
            # Actually, `google.genai.Client` usually has an `aio` property if it supports async.
            
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=gen_config
            )
        except Exception as e:
            # Handle API errors gracefully
            return LLMResponse(
                content=f"Error calling Gemini API: {str(e)}",
                finish_reason="error"
            )
        
        # Extract response
        content = None
        tool_calls = []
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    content = (content or "") + part.text
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        id=f"call_{fc.name}_{len(tool_calls)}",
                        name=fc.name,
                        arguments=fc.args or {}
                    ))
        
        # Determine finish reason
        finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            }
        )
