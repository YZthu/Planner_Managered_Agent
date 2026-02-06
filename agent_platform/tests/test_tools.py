"""
Test Suite for Core Tools
Tests web_search and spawn_subagent tools.
"""
import pytest


class TestWebSearchTool:
    """Tests for web_search tool."""
    
    def test_tool_has_required_attributes(self, core_plugin):
        """Web search tool should have name, description, parameters."""
        tools = core_plugin.get_tools()
        web_search = next((t for t in tools if t.name == "web_search"), None)
        
        assert web_search is not None
        assert web_search.name == "web_search"
        assert web_search.description is not None
        assert web_search.parameters is not None
    
    def test_tool_parameters_schema(self, core_plugin):
        """Web search parameters should have query field."""
        tools = core_plugin.get_tools()
        web_search = next((t for t in tools if t.name == "web_search"), None)
        
        assert "properties" in web_search.parameters
        assert "query" in web_search.parameters["properties"]


class TestSpawnSubagentTool:
    """Tests for spawn_subagent tool."""
    
    def test_tool_exists(self, core_plugin):
        """Spawn subagent tool should exist."""
        tools = core_plugin.get_tools()
        spawn = next((t for t in tools if t.name == "spawn_subagent"), None)
        
        assert spawn is not None
    
    def test_tool_parameters(self, core_plugin):
        """Spawn subagent should have task parameter."""
        tools = core_plugin.get_tools()
        spawn = next((t for t in tools if t.name == "spawn_subagent"), None)
        
        assert "task" in spawn.parameters.get("properties", {})


class TestMemoryTools:
    """Tests for memory plugin tools."""
    
    @pytest.mark.asyncio
    async def test_add_memory_tool(self, memory_plugin):
        """add_memory tool should exist and have correct interface."""
        tools = memory_plugin.get_tools()
        add_mem = next((t for t in tools if t.name == "add_memory"), None)
        
        assert add_mem is not None
        assert "text" in add_mem.parameters.get("properties", {})
    
    @pytest.mark.asyncio
    async def test_query_memory_tool(self, memory_plugin):
        """query_memory tool should exist and have correct interface."""
        tools = memory_plugin.get_tools()
        query_mem = next((t for t in tools if t.name == "query_memory"), None)
        
        assert query_mem is not None
        assert "query" in query_mem.parameters.get("properties", {})
    
    @pytest.mark.asyncio
    async def test_add_and_query_memory(self, memory_plugin):
        """Should be able to add and query memory."""
        tools = memory_plugin.get_tools()
        add_tool = next((t for t in tools if t.name == "add_memory"), None)
        query_tool = next((t for t in tools if t.name == "query_memory"), None)
        
        # Add a memory
        result = await add_tool.execute(
            text="Test memory: pytest functional test entry",
            metadata={"source": "pytest"}
        )
        assert result.success is True
        
        # Query for it
        result = await query_tool.execute(query="pytest functional test")
        assert result.success is True
        assert "pytest" in result.output.lower() or "test" in result.output.lower()
