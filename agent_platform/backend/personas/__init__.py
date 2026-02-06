"""
Personas Module
Dynamically loads persona system prompts and validates dependencies.
"""
import importlib
import logging
from typing import Optional, Dict, List, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fallback prompts (used if file loading fails)
from ..prompts import (
    DEFAULT_SYSTEM_PROMPT,
    DEEP_RESEARCH_SYSTEM_PROMPT,
    SUBAGENT_SYSTEM_PROMPT
)

_FALLBACK_PROMPTS = {
    "default": DEFAULT_SYSTEM_PROMPT,
    "deep_research": DEEP_RESEARCH_SYSTEM_PROMPT,
    "subagent": SUBAGENT_SYSTEM_PROMPT,
}


@dataclass
class PersonaRequirements:
    """Requirements for a persona to be eligible."""
    plugins: List[str]
    core_tools: List[str]      # Standalone tools from backend/tools/
    plugin_tools: List[str]    # Tools bundled inside plugins


@dataclass
class PersonaValidationResult:
    """Result of validating a persona's requirements."""
    persona_name: str
    eligible: bool
    missing_plugins: List[str]
    missing_core_tools: List[str]
    missing_plugin_tools: List[str]


def get_persona_requirements(persona_name: str) -> PersonaRequirements:
    """
    Load a persona's requirements.
    
    Args:
        persona_name: Name of the persona
    
    Returns:
        PersonaRequirements dataclass with plugins, core_tools, and plugin_tools lists.
    """
    try:
        module = importlib.import_module(f".{persona_name}", package="backend.personas")
        requirements = getattr(module, "REQUIREMENTS", {})
        return PersonaRequirements(
            plugins=requirements.get("plugins", []),
            core_tools=requirements.get("core_tools", []),
            plugin_tools=requirements.get("plugin_tools", []),
        )
    except (ImportError, AttributeError):
        return PersonaRequirements(plugins=[], core_tools=[], plugin_tools=[])


def validate_persona_requirements(
    persona_name: str,
    enabled_plugins: List[str],
    available_tools: Optional[List[str]] = None,
) -> PersonaValidationResult:
    """
    Validate if a persona's requirements are satisfied.
    
    Args:
        persona_name: Name of the persona to validate.
        enabled_plugins: List of enabled plugin names from config.
        available_tools: Optional list of available tool names. If None, only plugin check is performed.
    
    Returns:
        PersonaValidationResult with eligibility and any missing dependencies.
    """
    requirements = get_persona_requirements(persona_name)
    
    # Check plugins
    enabled_set = set(enabled_plugins)
    missing_plugins = [p for p in requirements.plugins if p not in enabled_set]
    
    # Check tools (if provided)
    missing_core_tools = []
    missing_plugin_tools = []
    if available_tools is not None:
        tools_set = set(available_tools)
        missing_core_tools = [t for t in requirements.core_tools if t not in tools_set]
        missing_plugin_tools = [t for t in requirements.plugin_tools if t not in tools_set]
    
    eligible = (
        len(missing_plugins) == 0 and 
        len(missing_core_tools) == 0 and 
        len(missing_plugin_tools) == 0
    )
    
    if not eligible:
        logger.warning(
            f"Persona '{persona_name}' requirements not satisfied. "
            f"Missing plugins: {missing_plugins}, "
            f"Missing core_tools: {missing_core_tools}, "
            f"Missing plugin_tools: {missing_plugin_tools}"
        )
    
    return PersonaValidationResult(
        persona_name=persona_name,
        eligible=eligible,
        missing_plugins=missing_plugins,
        missing_core_tools=missing_core_tools,
        missing_plugin_tools=missing_plugin_tools,
    )


def get_persona_prompt(persona_name: str) -> str:
    """
    Load a persona's system prompt by name.
    
    Args:
        persona_name: Name of the persona (e.g., 'default', 'deep_research', 'subagent')
    
    Returns:
        The system prompt string for that persona.
    """
    try:
        # Dynamically import the persona module
        module = importlib.import_module(f".{persona_name}", package="backend.personas")
        return getattr(module, "SYSTEM_PROMPT", _FALLBACK_PROMPTS.get(persona_name, DEFAULT_SYSTEM_PROMPT))
    except (ImportError, AttributeError):
        # Fallback if module doesn't exist
        return _FALLBACK_PROMPTS.get(persona_name, DEFAULT_SYSTEM_PROMPT)


def validate_persona_with_registry(persona_name: str) -> PersonaValidationResult:
    """
    Validate a persona's requirements using the plugin registry.
    
    This function auto-discovers enabled plugins and available tools
    from the global plugin_registry, so callers don't need to pass them manually.
    
    Args:
        persona_name: Name of the persona to validate.
    
    Returns:
        PersonaValidationResult with eligibility and any missing dependencies.
    """
    from ..config import config
    from ..core.plugins import plugin_registry
    
    enabled_plugins = config.plugins.enabled
    available_tools = plugin_registry.get_available_tool_names()
    
    return validate_persona_requirements(
        persona_name=persona_name,
        enabled_plugins=enabled_plugins,
        available_tools=available_tools,
    )
