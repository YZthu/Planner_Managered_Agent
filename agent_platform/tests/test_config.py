"""
Test Suite for Configuration System
Tests config loading, validation, and access patterns.
"""
import pytest
from pathlib import Path


class TestConfigLoading:
    """Tests for configuration file loading."""
    
    def test_config_loads_successfully(self, config):
        """Config should load without errors."""
        assert config is not None
    
    def test_config_has_all_sections(self, config):
        """Config should have all required sections."""
        assert hasattr(config, "llm")
        assert hasattr(config, "agent")
        assert hasattr(config, "memory")
        assert hasattr(config, "browser")
        assert hasattr(config, "network")
        assert hasattr(config, "security")
        assert hasattr(config, "personas")
        assert hasattr(config, "plugins")
        assert hasattr(config, "server")
        assert hasattr(config, "logging")


class TestLLMConfig:
    """Tests for LLM provider configuration."""
    
    def test_default_provider_exists(self, config):
        """Default provider should be set."""
        assert config.llm.default_provider in ["gemini", "deepseek", "openai"]
    
    def test_gemini_config(self, config):
        """Gemini config should have required fields."""
        assert config.llm.gemini.model is not None
        assert config.llm.gemini.temperature >= 0
        assert config.llm.gemini.max_tokens > 0
    
    def test_deepseek_config(self, config):
        """DeepSeek config should have required fields."""
        assert config.llm.deepseek.model is not None
        assert config.llm.deepseek.base_url.startswith("http")
    
    def test_openai_config(self, config):
        """OpenAI config should have required fields."""
        assert config.llm.openai.model is not None


class TestAgentConfig:
    """Tests for agent execution configuration."""
    
    def test_agent_limits(self, config):
        """Agent limits should be reasonable."""
        assert config.agent.max_concurrent_subagents >= 1
        assert config.agent.max_concurrent_subagents <= 20
        assert config.agent.max_tool_calls_per_turn >= 1
        assert config.agent.max_history_messages >= 1
    
    def test_subagent_timeout(self, config):
        """Subagent timeout should be set."""
        assert config.agent.subagent_timeout_seconds > 0


class TestPluginsConfig:
    """Tests for plugin configuration."""
    
    def test_plugins_enabled_list(self, config):
        """Plugins enabled should be a list."""
        assert isinstance(config.plugins.enabled, list)
    
    def test_core_plugin_enabled(self, config):
        """Core plugin should be enabled by default."""
        assert "core" in config.plugins.enabled


class TestPersonasConfig:
    """Tests for personas configuration."""
    
    def test_personas_enabled_list(self, config):
        """Personas enabled should be a list."""
        assert isinstance(config.personas.enabled, list)
    
    def test_default_persona_enabled(self, config):
        """Default persona should be enabled."""
        assert "default" in config.personas.enabled


class TestSecurityConfig:
    """Tests for security configuration."""
    
    def test_roles_defined(self, config):
        """Security roles should be defined."""
        assert "admin" in config.security.roles
        assert "user" in config.security.roles
    
    def test_default_role_exists(self, config):
        """Default role should exist in roles."""
        assert config.security.default_role in config.security.roles


class TestServerConfig:
    """Tests for server configuration."""
    
    def test_server_host(self, config):
        """Server host should be set."""
        assert config.server.host is not None
    
    def test_server_port(self, config):
        """Server port should be valid."""
        assert 1 <= config.server.port <= 65535
    
    def test_cors_origins(self, config):
        """CORS origins should be defined."""
        assert isinstance(config.server.cors_origins, list)
