"""
Core Plugin
Provides essential tools and system RPC methods.
"""
from typing import List
from ..core.plugins import BasePlugin
from ..tools.base import BaseTool
# Import your existing tools here
from ..tools.web_search import WebSearchTool
from ..tools.spawn_subagent import SpawnSubAgentTool  # Ensure this import path is correct

class CorePlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "core"

    def get_tools(self) -> List[BaseTool]:
        return [
            WebSearchTool(),
            SpawnSubAgentTool(),
        ]

    async def on_load(self):
        # Register core system methods if any additional ones are needed
        # (Gateway default methods are already registered in gateway.py, 
        # but we could move them here if we wanted full modularity)
        pass
