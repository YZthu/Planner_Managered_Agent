"""
Memory Plugin
Provides Long-Term Memory (RAG) capabilities using ChromaDB.
"""
import logging
from typing import List, Dict, Any, Optional
import os

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None

from ..core.plugins import BasePlugin
from ..tools.base import BaseTool, ToolResult
from ..config import config

logger = logging.getLogger(__name__)

class AddMemoryTool(BaseTool):
    def __init__(self, collection):
        self.collection = collection

    @property
    def name(self) -> str:
        return "add_memory"

    @property
    def description(self) -> str:
        return "Store a piece of information in long-term memory. Use this to remember facts about the user or the project."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The information to store."
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional key-value pairs for context (e.g. topic, source)."
                }
            },
            "required": ["text"]
        }

    async def execute(self, text: str, metadata: Dict[str, Any] = None, **kwargs) -> ToolResult:
        if not self.collection:
            return ToolResult(success=False, output="Memory not initialized.")
        
        try:
            import uuid
            mem_id = str(uuid.uuid4())
            self.collection.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[mem_id]
            )
            return ToolResult(
                success=True, 
                output=f"Stored in memory (ID: {mem_id})."
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to add memory: {str(e)}")


class QueryMemoryTool(BaseTool):
    def __init__(self, collection):
        self.collection = collection

    @property
    def name(self) -> str:
        return "query_memory"

    @property
    def description(self) -> str:
        return "Search long-term memory for relevant information."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query."
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3)."
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, n_results: int = 3, **kwargs) -> ToolResult:
        if not self.collection:
            return ToolResult(success=False, output="Memory not initialized.")
            
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Format results
            documents = results.get('documents', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            
            if not documents:
                return ToolResult(success=True, output="No relevant memories found.")
                
            formatted = []
            for i, doc in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                formatted.append(f"- {doc} (Context: {meta})")
                
            return ToolResult(success=True, output="Found in memory:\n" + "\n".join(formatted))
            
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to query memory: {str(e)}")


class MemoryPlugin(BasePlugin):
    def __init__(self):
        self.client = None
        self.collection = None
        
    @property
    def name(self) -> str:
        return "memory"

    async def on_load(self):
        if not chromadb:
            logger.warning("chromadb not installed. Memory plugin disabled.")
            return

        try:
            # Determine persistence path
            # config.memory might be a Box/Dict, check how config is implemented
            # Assuming config is loaded dict-like or object
            mem_config = getattr(config, 'memory', {})
            if isinstance(mem_config, dict):
                 path = mem_config.get("persist_directory", "./data/memory")
                 coll_name = mem_config.get("collection_name", "agent_memory")
            else:
                 path = getattr(mem_config, "persist_directory", "./data/memory")
                 coll_name = getattr(mem_config, "collection_name", "agent_memory")
            
            # Create data dir if not exists
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                
            self.client = chromadb.PersistentClient(path=path)
            self.collection = self.client.get_or_create_collection(name=coll_name)
            logger.info(f"Memory Plugin initialized at {path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Memory Plugin: {e}")
            self.collection = None

    def get_tools(self) -> List[BaseTool]:
        return [
            AddMemoryTool(self.collection),
            QueryMemoryTool(self.collection)
        ]
