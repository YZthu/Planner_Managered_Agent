"""
Test Suite for Agent Executor
Tests agent initialization, persona switching, and execution flow.
"""
import pytest
from backend.core.agent import AgentExecutor


class TestAgentInitialization:
    """Tests for AgentExecutor initialization."""
    
    def test_agent_creates_successfully(self):
        """Agent should instantiate with defaults."""
        agent = AgentExecutor()
        assert agent is not None
        assert agent.system_prompt is not None
    
    def test_agent_has_provider(self):
        """Agent should have a provider."""
        agent = AgentExecutor()
        assert agent.provider is not None
    
    def test_agent_loads_tools(self, core_plugin):
        """Agent should load tools from plugins."""
        agent = AgentExecutor()
        # Tools should be loaded from plugin registry
        assert isinstance(agent.tools, dict)
    
    def test_agent_role_default(self, config):
        """Agent should use default role from config."""
        agent = AgentExecutor()
        assert agent.role == config.security.default_role


class TestAgentPersonaSwitching:
    """Tests for persona switching functionality."""
    
    def test_set_persona_valid(self, plugin_registry_initialized):
        """Setting valid persona should succeed."""
        agent = AgentExecutor()
        result = agent.set_persona("default")
        assert result is True
    
    def test_set_persona_memory_manager(self, plugin_registry_initialized):
        """Setting memory_manager persona should work if memory plugin loaded."""
        agent = AgentExecutor()
        result = agent.set_persona("memory_manager")
        # Should succeed if memory plugin is enabled
        assert isinstance(result, bool)
    
    def test_set_persona_fallback(self, plugin_registry_initialized):
        """Setting ineligible persona should fallback to default."""
        # This test assumes browser plugin is not fully loaded
        from backend.core.plugins import plugin_registry
        
        agent = AgentExecutor()
        tool_names = plugin_registry.get_available_tool_names()
        
        # If browser tools are NOT available, deep_research should fallback
        if "browser_navigate" not in tool_names:
            result = agent.set_persona("deep_research")
            assert result is False  # Should fallback


class TestAgentToolDefinitions:
    """Tests for tool definition generation."""
    
    def test_get_tool_definitions(self):
        """Should return list of tool definitions."""
        agent = AgentExecutor()
        defs = agent.get_tool_definitions()
        assert isinstance(defs, list)
    
    def test_tool_definitions_structure(self):
        """Tool definitions should have proper structure."""
        agent = AgentExecutor()
        defs = agent.get_tool_definitions()
        
        if defs:
            first_def = defs[0]
            assert hasattr(first_def, "name")
            assert hasattr(first_def, "description")
            assert hasattr(first_def, "parameters")


class TestAgentSubagent:
    """Tests for subagent functionality."""
    
    def test_subagent_flag(self):
        """Subagent should have is_subagent flag set."""
        agent = AgentExecutor(is_subagent=True)
        assert agent.is_subagent is True
    
    def test_subagent_no_spawn_tool(self):
        """Subagents should not have spawn_subagent tool."""
        agent = AgentExecutor(is_subagent=True)
        assert "spawn_subagent" not in agent.tools


class TestAgentHistory:
    """Tests for conversation history management."""
    
    def test_clear_history(self):
        """Clear history should reset message history."""
        agent = AgentExecutor()
        agent._message_history.append("test")
        agent.clear_history()
        assert len(agent._message_history) == 0
