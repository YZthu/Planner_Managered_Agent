"""
Test Suite for Startup Module
Tests plugin initialization and persona validation at startup.
"""
import pytest
from backend.core.startup import (
    validate_enabled_personas,
    startup_sequence,
)


class TestPluginInitialization:
    """Tests for plugin initialization."""
    
    def test_plugins_registered(self, plugin_registry_initialized):
        """Plugins should be registered after initialization."""
        # Core plugin should always be registered
        assert plugin_registry_initialized.get_plugin("core") is not None


class TestPersonaValidation:
    """Tests for persona validation at startup."""
    
    def test_validate_enabled_personas(self, plugin_registry_initialized):
        """validate_enabled_personas should return dict."""
        result = validate_enabled_personas()
        assert isinstance(result, dict)
    
    def test_validation_returns_booleans(self, plugin_registry_initialized):
        """Validation results should be booleans."""
        result = validate_enabled_personas()
        for persona_name, eligible in result.items():
            assert isinstance(eligible, bool), f"{persona_name} eligibility is not bool"
    
    def test_default_always_eligible(self, plugin_registry_initialized):
        """Default persona should always be eligible."""
        result = validate_enabled_personas()
        assert result.get("default") is True


class TestStartupSequence:
    """Tests for full startup sequence."""
    
    def test_startup_sequence_returns_dict(self, event_loop):
        """startup_sequence should return status dict."""
        result = event_loop.run_until_complete(startup_sequence())
        assert isinstance(result, dict)
        assert "plugins" in result
        assert "personas" in result
    
    def test_startup_sequence_plugins_list(self, event_loop):
        """Startup result should contain plugins list."""
        result = event_loop.run_until_complete(startup_sequence())
        assert isinstance(result["plugins"], list)
    
    def test_startup_sequence_personas_dict(self, event_loop):
        """Startup result should contain personas status dict."""
        result = event_loop.run_until_complete(startup_sequence())
        assert isinstance(result["personas"], dict)
