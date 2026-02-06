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

    @property
    def hooks(self) -> Dict[str, Any]:
        """Dictionary of event name to handler method"""
        return {}

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
        self._hooks: Dict[str, List[Any]] = {}
        self._loaded = False

    def register_hook(self, event: str, handler: Any):
        """Register a hook handler"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
        logger.debug(f"Registered hook for {event}")

    async def trigger_hook(self, event: str, **kwargs):
        """Trigger all handlers for an event"""
        if event in self._hooks:
            for handler in self._hooks[event]:
                try:
                    import inspect
                    if inspect.iscoroutinefunction(handler):
                        await handler(**kwargs)
                    else:
                        handler(**kwargs)
                except Exception as e:
                    logger.error(f"Error in hook {event}: {e}")

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
                
                # Register hooks
                for event, handler in plugin.hooks.items():
                    self.register_hook(event, handler)
                    
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

    def get_available_tool_names(self) -> List[str]:
        """Get names of all available tools from loaded plugins."""
        return [tool.name for tool in self.get_all_tools()]

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

# Global Instance
plugin_registry = PluginRegistry()
