"""
Test Suite for Persona System
Tests persona loading, requirements, and validation.
"""
import pytest
from backend.config import config
from backend.personas import (
    get_persona_prompt,
    get_persona_requirements,
    validate_persona_requirements,
    validate_persona_with_registry,
)


class TestPersonaLoading:
    """Tests for persona prompt loading."""
    
    def test_load_default_persona(self):
        """Default persona should always load successfully."""
        prompt = get_persona_prompt("default")
        assert prompt is not None
        assert len(prompt) > 100
        assert "assistant" in prompt.lower() or "agent" in prompt.lower()
    
    def test_load_all_enabled_personas(self, enabled_personas):
        """All enabled personas should load without errors."""
        for persona_name in enabled_personas:
            prompt = get_persona_prompt(persona_name)
            assert prompt is not None, f"Persona '{persona_name}' failed to load"
            assert len(prompt) > 50, f"Persona '{persona_name}' has insufficient content"
    
    def test_nonexistent_persona_returns_none_or_fallback(self):
        """Unknown personas should return None or fallback."""
        prompt = get_persona_prompt("nonexistent_persona_xyz")
        # Should either return None or a fallback prompt
        # (depends on implementation)
        assert prompt is None or len(prompt) > 0


class TestPersonaRequirements:
    """Tests for persona requirements loading."""
    
    def test_requirements_structure(self, enabled_personas):
        """All personas should have properly structured requirements."""
        for persona_name in enabled_personas:
            reqs = get_persona_requirements(persona_name)
            assert hasattr(reqs, "plugins"), f"{persona_name} missing 'plugins'"
            assert hasattr(reqs, "core_tools"), f"{persona_name} missing 'core_tools'"
            assert hasattr(reqs, "plugin_tools"), f"{persona_name} missing 'plugin_tools'"
            assert isinstance(reqs.plugins, list)
            assert isinstance(reqs.core_tools, list)
            assert isinstance(reqs.plugin_tools, list)
    
    def test_default_persona_requires_core(self):
        """Default persona should require the 'core' plugin."""
        reqs = get_persona_requirements("default")
        assert "core" in reqs.plugins
    
    def test_memory_manager_requires_memory_plugin(self):
        """Memory manager should require memory plugin and tools."""
        reqs = get_persona_requirements("memory_manager")
        assert "memory" in reqs.plugins
        assert "add_memory" in reqs.plugin_tools
        assert "query_memory" in reqs.plugin_tools
    
    def test_deep_research_requires_browser(self):
        """Deep research should require browser plugin tools."""
        reqs = get_persona_requirements("deep_research")
        assert "browser" in reqs.plugins
        assert "browser_navigate" in reqs.plugin_tools or "browser_content" in reqs.plugin_tools


class TestPersonaValidation:
    """Tests for persona requirements validation."""
    
    def test_validation_with_all_plugins(self, enabled_plugins):
        """Validation should pass when all plugins are enabled."""
        result = validate_persona_requirements("default", enabled_plugins)
        assert result.eligible is True
        assert result.missing_plugins == []
    
    def test_validation_detects_missing_plugin(self):
        """Validation should detect missing plugins."""
        # deep_research requires 'browser' plugin
        result = validate_persona_requirements("deep_research", ["core"])
        assert result.eligible is False
        assert "browser" in result.missing_plugins
    
    def test_validation_with_tool_check(self):
        """Validation should check tools when available_tools is provided."""
        result = validate_persona_requirements(
            "memory_manager",
            enabled_plugins=["memory"],
            available_tools=[]  # Empty - no tools available
        )
        assert result.eligible is False
        assert "add_memory" in result.missing_plugin_tools or "query_memory" in result.missing_plugin_tools
    
    def test_validation_passes_with_correct_tools(self):
        """Validation should pass when all tools are available."""
        result = validate_persona_requirements(
            "memory_manager",
            enabled_plugins=["memory"],
            available_tools=["add_memory", "query_memory"]
        )
        assert result.eligible is True
    
    def test_subagent_has_no_requirements(self):
        """Subagent persona should have minimal requirements."""
        reqs = get_persona_requirements("subagent")
        assert reqs.plugins == []
        assert reqs.core_tools == []
        assert reqs.plugin_tools == []


class TestPersonaValidationWithRegistry:
    """Tests for validate_persona_with_registry (requires initialized plugins)."""
    
    def test_validate_with_registry(self, plugin_registry_initialized):
        """Should validate using actual plugin registry state."""
        result = validate_persona_with_registry("default")
        assert result.eligible is True
    
    def test_registry_provides_tool_names(self, plugin_registry_initialized):
        """Plugin registry should correctly provide tool names."""
        tool_names = plugin_registry_initialized.get_available_tool_names()
        assert "web_search" in tool_names
        assert "spawn_subagent" in tool_names
