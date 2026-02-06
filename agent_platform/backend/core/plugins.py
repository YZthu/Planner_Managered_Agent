"""
Plugin System
Base classes and registry for extending agent capabilities.
"""
from typing import List, Dict, Type, Any, Optional
from abc import ABC, abstractmethod
import logging

from ..tools.base import BaseTool

logger = logging.getLogger(__name__)

class BasePlugin(ABC):
    """
    Abstract base class for plugins.
    Plugins can provide Tools, RPC methods, and Listeners.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name"""
        pass

    def get_tools(self) -> List[BaseTool]:
        """Return list of tools provided by this plugin"""
        return []

    async def on_load(self):
        """Called when plugin is loaded. Use to register RPC methods."""
        pass

    async def on_shutdown(self):
        """Called on shutdown"""
        pass


class PluginRegistry:
    """
    Singleton registry for managing plugins.
    """
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._loaded = False

    def register_plugin(self, plugin: BasePlugin):
        """Register a plugin instance"""
        if plugin.name in self._plugins:
            logger.warning(f"Plugin {plugin.name} already registered. Overwriting.")
        self._plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin.name}")

    async def initialize(self):
        """Initialize all registered plugins"""
        # Note: We don't return early if self._loaded because new plugins might have been added
        
        for name, plugin in self._plugins.items():
            if getattr(plugin, "_initialized", False):
                continue
                
            try:
                await plugin.on_load()
                plugin._initialized = True
                logger.info(f"Initialized plugin: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize plugin {name}: {e}", exc_info=True)
        
        self._loaded = True

    def get_all_tools(self) -> List[BaseTool]:
        """Aggregate tools from all plugins"""
        tools = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

# Global Instance
plugin_registry = PluginRegistry()
