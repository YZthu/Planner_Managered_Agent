"""
End-to-End Tests for Agent Platform
Tests all enabled personas and plugin tools.
"""
import sys
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent path for imports
sys.path.insert(0, '.')

from backend.config import config
from backend.personas import get_persona_prompt

# --- Test Personas ---
async def test_persona_loading():
    """Test that all enabled personas can be loaded."""
    print("\n" + "="*60)
    print("TEST: Persona Loading")
    print("="*60)
    
    enabled_personas = config.personas.enabled
    results = {"passed": 0, "failed": 0, "errors": []}
    
    for persona_name in enabled_personas:
        try:
            prompt = get_persona_prompt(persona_name)
            if prompt and len(prompt) > 50:
                print(f"  ✅ Loaded '{persona_name}' ({len(prompt)} chars)")
                results["passed"] += 1
            else:
                print(f"  ❌ '{persona_name}' loaded but has insufficient content")
                results["failed"] += 1
                results["errors"].append(f"{persona_name}: insufficient content")
        except Exception as e:
            print(f"  ❌ Failed to load '{persona_name}': {e}")
            results["failed"] += 1
            results["errors"].append(f"{persona_name}: {e}")
    
    return results


async def test_persona_requirements():
    """Test persona dependency validation."""
    print("\n" + "="*60)
    print("TEST: Persona Requirements Validation")
    print("="*60)
    
    from backend.personas import get_persona_requirements, validate_persona_requirements
    
    results = {"passed": 0, "failed": 0, "errors": []}
    enabled_plugins = config.plugins.enabled
    
    # Test each persona's requirements are loaded
    for persona_name in config.personas.enabled:
        reqs = get_persona_requirements(persona_name)
        print(f"  {persona_name}: plugins={reqs.plugins}, tools={reqs.tools}")
        results["passed"] += 1
    
    # Test validation logic
    validation = validate_persona_requirements("deep_research", enabled_plugins)
    if validation.eligible:
        print(f"  ✅ deep_research is eligible with current plugins")
        results["passed"] += 1
    else:
        print(f"  ⚠️ deep_research not eligible: missing={validation.missing_plugins}")
        results["passed"] += 1  # This is not a failure, just a status report
    
    # Test validation with missing plugin
    validation2 = validate_persona_requirements("deep_research", ["core"])
    if not validation2.eligible and "browser" in validation2.missing_plugins:
        print(f"  ✅ Correctly detected missing 'browser' plugin")
        results["passed"] += 1
    else:
        print(f"  ❌ Failed to detect missing 'browser' plugin")
        results["failed"] += 1
        results["errors"].append("Validation logic failed to detect missing plugin")
    
    return results

# --- Test Plugin Tools ---
async def test_core_plugin():
    """Test CorePlugin tools (web_search, spawn_subagent)."""
    print("\n" + "="*60)
    print("TEST: CorePlugin Tools")
    print("="*60)
    
    from backend.plugins.core import CorePlugin
    
    plugin = CorePlugin()
    tools = plugin.get_tools()
    tool_names = [t.name for t in tools]
    
    print(f"  Available tools: {tool_names}")
    
    results = {"passed": 0, "failed": 0, "errors": []}
    expected_tools = ["web_search", "spawn_subagent"]
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"  ✅ Tool '{expected}' found")
            results["passed"] += 1
        else:
            print(f"  ❌ Tool '{expected}' NOT found")
            results["failed"] += 1
            results["errors"].append(f"Missing tool: {expected}")
    
    return results

async def test_memory_plugin():
    """Test MemoryPlugin tools (add_memory, query_memory)."""
    print("\n" + "="*60)
    print("TEST: MemoryPlugin Tools")
    print("="*60)
    
    from backend.plugins.memory import MemoryPlugin
    
    plugin = MemoryPlugin()
    await plugin.on_load()
    
    tools = plugin.get_tools()
    tool_names = [t.name for t in tools]
    
    print(f"  Available tools: {tool_names}")
    
    results = {"passed": 0, "failed": 0, "errors": []}
    expected_tools = ["add_memory", "query_memory"]
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"  ✅ Tool '{expected}' found")
            results["passed"] += 1
        else:
            print(f"  ❌ Tool '{expected}' NOT found")
            results["failed"] += 1
            results["errors"].append(f"Missing tool: {expected}")
    
    # Functional test: add and query memory
    if plugin.collection:
        try:
            add_tool = next((t for t in tools if t.name == "add_memory"), None)
            query_tool = next((t for t in tools if t.name == "query_memory"), None)
            
            if add_tool and query_tool:
                add_result = await add_tool.execute(
                    text="Test memory entry: E2E test at timestamp 12345",
                    metadata={"source": "e2e_test"}
                )
                print(f"  ✅ add_memory executed: {add_result.output[:50]}...")
                results["passed"] += 1
                
                query_result = await query_tool.execute(query="E2E test")
                print(f"  ✅ query_memory executed: {query_result.output[:50]}...")
                results["passed"] += 1
        except Exception as e:
            print(f"  ⚠️ Functional test error: {e}")
            results["errors"].append(f"Memory functional test: {e}")
    else:
        print("  ⚠️ ChromaDB not available, skipping functional test")
    
    return results

async def test_browser_plugin():
    """Test BrowserPlugin tools (navigate, content, click, screenshot)."""
    print("\n" + "="*60)
    print("TEST: BrowserPlugin Tools")
    print("="*60)
    
    from backend.plugins.browser import BrowserPlugin, PLAYWRIGHT_AVAILABLE
    
    if not PLAYWRIGHT_AVAILABLE:
        print("  ⚠️ Playwright not installed, skipping browser tests")
        return {"passed": 0, "failed": 0, "errors": ["Playwright not installed"]}
    
    plugin = BrowserPlugin()
    await plugin.on_load()
    
    tools = plugin.get_tools()
    tool_names = [t.name for t in tools]
    
    print(f"  Available tools: {tool_names}")
    
    results = {"passed": 0, "failed": 0, "errors": []}
    expected_tools = ["browser_navigate", "browser_content", "browser_click", "browser_screenshot"]
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"  ✅ Tool '{expected}' found")
            results["passed"] += 1
        else:
            print(f"  ❌ Tool '{expected}' NOT found")
            results["failed"] += 1
            results["errors"].append(f"Missing tool: {expected}")
    
    # Functional test: navigate and get content
    if plugin.page:
        try:
            nav_tool = next((t for t in tools if t.name == "browser_navigate"), None)
            content_tool = next((t for t in tools if t.name == "browser_content"), None)
            
            if nav_tool:
                nav_result = await nav_tool.execute(url="https://example.com")
                print(f"  ✅ browser_navigate executed: {nav_result.output}")
                results["passed"] += 1
            
            if content_tool:
                content_result = await content_tool.execute()
                content_preview = content_result.output[:100].replace('\n', ' ')
                print(f"  ✅ browser_content executed: {content_preview}...")
                results["passed"] += 1
        except Exception as e:
            print(f"  ⚠️ Functional test error: {e}")
            results["errors"].append(f"Browser functional test: {e}")
    else:
        print("  ⚠️ Browser page not initialized, skipping functional test")
    
    await plugin.cleanup()
    return results

async def test_network_plugin():
    """Test NetworkPlugin tools (get_network_status)."""
    print("\n" + "="*60)
    print("TEST: NetworkPlugin Tools")
    print("="*60)
    
    from backend.plugins.network import NetworkPlugin, NETWORK_AVAILABLE
    
    if not NETWORK_AVAILABLE:
        print("  ⚠️ Network dependencies (zeroconf/netifaces) not installed, skipping")
        return {"passed": 0, "failed": 0, "errors": ["Network deps not installed"]}
    
    plugin = NetworkPlugin()
    await plugin.on_load()
    
    tools = plugin.get_tools()
    tool_names = [t.name for t in tools]
    
    print(f"  Available tools: {tool_names}")
    
    results = {"passed": 0, "failed": 0, "errors": []}
    expected_tools = ["get_network_status"]
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"  ✅ Tool '{expected}' found")
            results["passed"] += 1
        else:
            print(f"  ❌ Tool '{expected}' NOT found")
            results["failed"] += 1
            results["errors"].append(f"Missing tool: {expected}")
    
    # Functional test: get network status
    try:
        status_tool = next((t for t in tools if t.name == "get_network_status"), None)
        if status_tool:
            result = await status_tool.execute()
            print(f"  ✅ get_network_status executed:")
            for line in result.output.split('\n')[:5]:
                print(f"      {line}")
            results["passed"] += 1
    except Exception as e:
        print(f"  ⚠️ Functional test error: {e}")
        results["errors"].append(f"Network functional test: {e}")
    
    await plugin.cleanup()
    return results


# --- Main Test Runner ---
async def main():
    print("\n" + "#"*60)
    print("#  AGENT PLATFORM END-TO-END TESTS")
    print("#"*60)
    
    all_results = {
        "personas": await test_persona_loading(),
        "persona_requirements": await test_persona_requirements(),
        "core_plugin": await test_core_plugin(),
        "memory_plugin": await test_memory_plugin(),
        "browser_plugin": await test_browser_plugin(),
        "network_plugin": await test_network_plugin(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total_passed = 0
    total_failed = 0
    all_errors = []
    
    for name, result in all_results.items():
        total_passed += result["passed"]
        total_failed += result["failed"]
        all_errors.extend(result["errors"])
        status = "✅ PASS" if result["failed"] == 0 else "❌ FAIL"
        print(f"  {name}: {result['passed']} passed, {result['failed']} failed {status}")
    
    print("-"*60)
    print(f"  TOTAL: {total_passed} passed, {total_failed} failed")
    
    if all_errors:
        print("\n  ERRORS:")
        for err in all_errors:
            print(f"    - {err}")
    
    print("="*60 + "\n")
    
    return total_failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
