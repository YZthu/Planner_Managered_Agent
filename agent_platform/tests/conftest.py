"""
Pytest Configuration and Fixtures
Shared fixtures for all test modules.
"""
import sys
import asyncio
import pytest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def config():
    """Load and return the platform configuration."""
    from backend.config import config
    return config


@pytest.fixture(scope="session")
def plugin_registry_initialized(event_loop):
    """Initialize plugins once per test session and return registry."""
    from backend.core.startup import initialize_plugins
    from backend.core.plugins import plugin_registry
    
    # Run async initialization in the event loop
    event_loop.run_until_complete(initialize_plugins())
    return plugin_registry


@pytest.fixture
def core_plugin():
    """Return an uninitialized CorePlugin instance."""
    from backend.plugins.core import CorePlugin
    return CorePlugin()


@pytest.fixture
def memory_plugin(event_loop, config, tmp_path):
    """Return an initialized MemoryPlugin instance."""
    from backend.plugins.memory import MemoryPlugin
    
    # Use temporary directory for tests
    old_dir = config.memory.persist_directory
    config.memory.persist_directory = str(tmp_path / "test_memory")
    
    plugin = MemoryPlugin()
    event_loop.run_until_complete(plugin.on_load())
    
    yield plugin
    
    # Restore original dir
    config.memory.persist_directory = old_dir


@pytest.fixture
def browser_plugin(event_loop):
    """Return an initialized BrowserPlugin instance (if available)."""
    from backend.plugins.browser import BrowserPlugin, PLAYWRIGHT_AVAILABLE
    
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed")
    
    plugin = BrowserPlugin()
    event_loop.run_until_complete(plugin.on_load())
    yield plugin
    event_loop.run_until_complete(plugin.cleanup())


@pytest.fixture
def network_plugin(event_loop):
    """Return an initialized NetworkPlugin instance (if available)."""
    from backend.plugins.network import NetworkPlugin, NETWORK_AVAILABLE
    
    if not NETWORK_AVAILABLE:
        pytest.skip("Network dependencies not installed")
    
    plugin = NetworkPlugin()
    event_loop.run_until_complete(plugin.on_load())
    yield plugin
    event_loop.run_until_complete(plugin.cleanup())


@pytest.fixture
def agent_executor():
    """Return a fresh AgentExecutor instance."""
    from backend.core.agent import AgentExecutor
    return AgentExecutor()


@pytest.fixture
def enabled_plugins(config):
    """Return list of enabled plugin names from config."""
    return config.plugins.enabled


@pytest.fixture
def enabled_personas(config):
    """Return list of enabled persona names from config."""
    return config.personas.enabled
