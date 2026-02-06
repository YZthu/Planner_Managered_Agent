"""
Test Suite for Network Plugin
Tests mDNS registration and network status reporting.
"""
import pytest
from backend.plugins.network import NetworkPlugin


@pytest.mark.asyncio
async def test_network_lifecycle(network_plugin):
    """Test full lifecycle of network plugin."""
    # network_plugin fixture handles on_load and cleanup
    assert network_plugin is not None
    
    # Check if zeroconf initialized (may be None if no network interfaces available)
    # But usually passes on local machine
    if network_plugin.zeroconf:
        assert network_plugin.service_info is not None
    
    tools = network_plugin.get_tools()
    status_tool = next((t for t in tools if t.name == "get_network_status"), None)
    assert status_tool is not None
    
    # Test tool execution
    result = await status_tool.execute()
    assert result.success is True
    assert "Network Status" in result.output
    assert "mDNS Service" in result.output


def test_network_plugin_name():
    """Test network plugin name property."""
    plugin = NetworkPlugin()
    assert plugin.name == "network"


@pytest.mark.asyncio
async def test_network_mdns_start(config):
    """Test manual mDNS start if possible."""
    from backend.plugins.network import NETWORK_AVAILABLE
    if not NETWORK_AVAILABLE:
        pytest.skip("Network dependencies not available")
        
    plugin = NetworkPlugin()
    # Mock config for test
    config.network.enable_mdns = True
    config.network.hostname = "test-agent"
    
    try:
        await plugin.on_load()
        if plugin.zeroconf:
            assert "test-agent" in str(plugin.service_info.name)
    finally:
        await plugin.cleanup()
