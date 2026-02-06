"""
Startup Module
Plugin initialization and persona validation for application startup.
"""
import logging
from typing import Dict, List, Type

from .plugins import plugin_registry, BasePlugin
from ..config import config

logger = logging.getLogger(__name__)


# Plugin class registry - maps plugin names to their classes
_PLUGIN_CLASSES: Dict[str, Type[BasePlugin]] = {}


def register_plugin_class(name: str, plugin_class: Type[BasePlugin]):
    """Register a plugin class for initialization."""
    _PLUGIN_CLASSES[name] = plugin_class


def _load_plugin_classes():
    """Lazy load plugin classes to avoid circular imports."""
    global _PLUGIN_CLASSES
    if _PLUGIN_CLASSES:
        return
    
    # Import here to avoid circular imports
    from ..plugins.core import CorePlugin
    from ..plugins.memory import MemoryPlugin
    from ..plugins.browser import BrowserPlugin
    from ..plugins.network import NetworkPlugin
    
    _PLUGIN_CLASSES = {
        "core": CorePlugin,
        "memory": MemoryPlugin,
        "browser": BrowserPlugin,
        "network": NetworkPlugin,
    }


async def initialize_plugins(enabled_plugins: List[str] = None):
    """
    Register and initialize all enabled plugins.
    
    Args:
        enabled_plugins: List of plugin names to enable. Defaults to config.plugins.enabled.
    """
    _load_plugin_classes()
    
    plugins_to_enable = enabled_plugins or config.plugins.enabled
    
    for plugin_name in plugins_to_enable:
        if plugin_name in _PLUGIN_CLASSES:
            plugin_registry.register_plugin(_PLUGIN_CLASSES[plugin_name]())
        else:
            logger.warning(f"Unknown plugin: {plugin_name}")
    
    await plugin_registry.initialize()
    logger.info(f"Plugins initialized: {plugins_to_enable}")


def validate_enabled_personas(personas: List[str] = None) -> Dict[str, bool]:
    """
    Validate all enabled personas and log warnings for ineligible ones.
    
    Args:
        personas: List of persona names to validate. Defaults to config.personas.enabled.
    
    Returns:
        Dict mapping persona name to eligibility (True/False).
    """
    from ..personas import validate_persona_with_registry, get_persona_requirements
    
    personas_to_validate = personas or config.personas.enabled
    results = {}
    
    logger.info(f"Validating personas: {personas_to_validate}")
    
    for persona_name in personas_to_validate:
        result = validate_persona_with_registry(persona_name)
        results[persona_name] = result.eligible
        
        if result.eligible:
            logger.info(f"  ✅ {persona_name}: eligible")
        else:
            logger.warning(
                f"  ⚠️  {persona_name}: NOT eligible - "
                f"missing_plugins={result.missing_plugins}, "
                f"missing_core_tools={result.missing_core_tools}, "
                f"missing_plugin_tools={result.missing_plugin_tools}"
            )
    
    return results


async def startup_sequence():
    """
    Full startup sequence: initialize plugins and validate personas.
    
    Returns:
        Dict with 'plugins' (list of enabled plugins) and 'personas' (eligibility dict).
    """
    await initialize_plugins()
    persona_status = validate_enabled_personas()
    
    return {
        "plugins": config.plugins.enabled,
        "personas": persona_status,
    }
